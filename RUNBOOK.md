# Operational Runbook

Operating procedures for the Autonomous Adaptive Trading Intelligence Platform.

> **Standing posture: PAPER.** Live trading is disabled. It cannot be enabled by
> code, by the API, or by any agent. Enabling it requires dual-role human
> sign-off *and* an out-of-band operator environment variable. If you are not
> deliberately executing the promotion procedure in section 5, the answer to
> "should this go live?" is no.

---

## 1. Modes

| Mode | Meaning | Capital at risk |
|------|---------|-----------------|
| `DISABLED` | Nothing runs. Default cold state. | none |
| `RESEARCH` | Backtests, analysis, no order flow. | none |
| `BACKTEST` | Historical simulation only. | none |
| `PAPER` | **Normal operating mode.** Simulated fills. | none |
| `SHADOW` | Real signals, intents recorded and compared to real prices. No broker connection exists. | none |
| `LIVE` | Real orders. **Not authorized.** | real |
| `EMERGENCY_STOP` | Everything halted. Manual reset required. | none |

Check the current mode:

```
GET /system/mode
GET /governance/live-posture
```

---

## 2. Daily operations

### 2.1 Pre-market (before 09:30 ET)
1. `GET /health` — confirm `status=ok` and `mode=PAPER`.
2. `GET /system/mode` — confirm `emergency_stopped=false`.
3. `GET /risk/summary` — confirm no breached limits carried over.
4. Confirm the news pipeline is polling (recent items in `GET /research/news`).
5. Confirm the paper trading loop is running (`status()` reports `running=true`).

### 2.2 During the session
- The loop trades only during the `REGULAR` session phase.
- The risk engine has absolute veto. A veto is expected behaviour, not a fault.
- Watch for `circuit_breaker`, `kill_switch`, and `degradation` alerts.

### 2.3 Post-close
1. The daily review runs automatically after the close.
2. On Fridays the weekly review also runs.
3. Review learning-engine *proposals*. Nothing is auto-applied — every proposed
   parameter change requires explicit approval.

---

## 3. Incident response

### 3.1 Kill switch — halt everything now

```
POST /system/kill   { "reason": "<why>", "actor": "<who>" }
```

Effect: mode becomes `EMERGENCY_STOP`. Every loop aborts on its next tick. No
transition out of emergency stop is possible except a manual reset.

Reset (only after the cause is understood and documented):

```
POST /system/reset  { "reason": "<resolution>", "actor": "<who>" }
```

### 3.2 Symptom triage

| Symptom | First checks | Action |
|---------|--------------|--------|
| No signals generated | session phase, data freshness, strategy status | verify market open; check data validator rejects |
| Every trade vetoed | `GET /risk/summary`, trade quality filter reasons | expected if a limit is breached; confirm limits are correct |
| Drawdown alert | drawdown monitor, open positions | kill switch if limits are breached; do not override |
| Divergence alert (shadow) | `divergence_report()` | if > 10%, the SHADOW gate fails — investigate before any promotion |
| Degradation alert | strategy degradation monitor | demote the strategy; revoke any live authorization |
| API errors | logs, `GET /health` | restart the API; the loop is independent of the API |

### 3.3 Any live authorization in force?

If a degradation alert, drawdown breach or risk veto occurs while an
authorization is active, revoke it immediately:

```
POST /governance/live-authorization/{strategy}/revoke  { "reason": "<why>" }
```

This also revokes the underlying approval record, so promotion must restart from
the beginning.

---

## 4. Strategy promotion pipeline

A strategy must clear every stage **in order**. No stage may be skipped.

```
RESEARCH → HYPOTHESIS → BACKTEST → OUT_OF_SAMPLE → WALK_FORWARD
         → MONTE_CARLO → PAPER → SHADOW → RISK_REVIEW → APPROVAL → LIVE
```

Automated gate thresholds live in `validation/pipeline.py::PromotionGates` and
are configuration, never hardcoded at the call site. Key gates:

- **BACKTEST** — ≥30 trades, Sharpe ≥0.5, max DD ≤25%, profit factor ≥1.2,
  positive expectancy.
- **OUT_OF_SAMPLE** — Sharpe ≥0.3, max DD ≤30%.
- **WALK_FORWARD** — efficiency ≥0.4, passes in ≥3 windows.
- **MONTE_CARLO** — ruin probability <5%, p95 drawdown ≤35%.
- **PAPER** — ≥50 trades over ≥14 days, Sharpe ≥0.3, max DD ≤20%.
- **SHADOW** — divergence ≤10% (worse of price and P&L divergence).
- **RISK_REVIEW** — all 12 checklist items satisfied.
- **APPROVAL** — dual-role human sign-off.

---

## 5. Live promotion procedure (currently not authorized)

All six conditions must hold **simultaneously**. The gate is deny-by-default and
reports the exact unmet conditions.

1. **Automated validation complete** — the strategy is at the `APPROVAL` stage
   with every prior gate passed in sequence.
2. **Risk review passed** — work through the checklist:
   ```
   GET  /governance/risk-review/{strategy}
   POST /governance/risk-review/{strategy}/attest
   POST /governance/risk-review/{strategy}/review
   ```
   Automated items are evaluated from collected evidence. The five manual items
   (capital allocation, failure modes, rollback plan, monitoring readiness,
   broker account verification) each require a **named** human attester.
3. **Dual-role human approval**:
   ```
   POST /governance/approvals              { "strategy": "..." }
   POST /governance/approvals/{id}/vote    { role: RISK_OFFICER,    approved: true }
   POST /governance/approvals/{id}/vote    { role: PORTFOLIO_OWNER, approved: true }
   ```
   One person cannot authorise alone. The `SYSTEM` role may veto but may never
   approve. Any single rejection is terminal. Approvals expire after 72 hours.
4. **Out-of-band operator authorisation** — an operator sets
   `LIVE_TRADING_AUTHORIZED=true` in the deployment environment. No API call and
   no code path can set this.
5. **Capital cap** — a platform ceiling must be configured and the requested
   allocation must sit inside it.
6. **System healthy** — not emergency-stopped.

Evaluate the gate (this never enables anything):

```
POST /governance/live-authorization/evaluate
```

A successful evaluation issues a **time-boxed (24h), capital-capped**
authorization. It expires automatically and must be re-issued. Expiry is a
feature: there is no such thing as a permanent live grant.

### Rollback
1. Revoke the authorization (section 3.3).
2. Transition the strategy back to `PAPER`.
3. Flatten positions through the normal execution path.
4. Record the reason in the approval audit log (`GET /governance/audit`).

---

## 6. Audit trail

Every governance action is appended to an immutable ledger. Records are never
overwritten — superseding a decision creates a new record referencing the old.

```
GET /governance/audit
GET /governance/approvals
GET /system/history
```

---

## 7. Configuration and secrets

- All credentials come from the environment. Nothing is hardcoded.
- Required for market data: Alpaca key/secret (paper endpoint by default).
- Optional: `ABACUSAI_API_KEY` for LLM-assisted analysis. Absent ⇒ those
  features degrade gracefully and the platform keeps running.
- `LIVE_TRADING_AUTHORIZED` — must be absent or false in every environment that
  is not deliberately executing section 5.

---

## 8. Escalation

| Severity | Trigger | Action |
|----------|---------|--------|
| P0 | Unexplained real-money exposure, or the kill switch fails | kill switch, disconnect broker credentials, page the portfolio owner |
| P1 | Drawdown circuit breaker tripped, or a live authorization active during an incident | revoke authorization, halt trading, notify the risk officer |
| P2 | Strategy degradation, persistent shadow divergence | demote the strategy, open an approval revocation |
| P3 | Data gaps, API errors, news pipeline stalls | fix in-session; note in the daily review |
