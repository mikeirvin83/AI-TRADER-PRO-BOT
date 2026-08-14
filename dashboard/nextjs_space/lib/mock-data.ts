// Comprehensive mock data for the trading intelligence dashboard

export const MOCK_SYSTEM_STATUS = {
  trading_mode: 'PAPER' as const,
  market_status: 'Open' as const,
  system_health: 'HEALTHY' as const,
  uptime_hours: 142.5,
  last_heartbeat: new Date().toISOString(),
  api_connected: true,
  ws_connected: false,
};

export const MOCK_ACCOUNT = {
  portfolio_value: 127543.82,
  cash: 45231.19,
  buying_power: 90462.38,
  daily_pnl: 1234.56,
  daily_pnl_pct: 0.98,
  weekly_pnl: 3456.78,
  weekly_pnl_pct: 2.78,
  monthly_pnl: 8765.43,
  monthly_pnl_pct: 7.38,
  max_drawdown: -3.21,
  equity: 127543.82,
  long_market_value: 62312.63,
  short_market_value: 0,
};

export const MOCK_MARKET_OVERVIEW = [
  { symbol: 'SPY', name: 'S&P 500 ETF', price: 452.18, change: 1.23, change_pct: 0.27, volume: 78453210 },
  { symbol: 'QQQ', name: 'NASDAQ 100 ETF', price: 387.54, change: 2.87, change_pct: 0.75, volume: 45312870 },
  { symbol: 'BTC/USD', name: 'Bitcoin', price: 43521.30, change: -312.45, change_pct: -0.71, volume: 28453000000 },
  { symbol: 'ETH/USD', name: 'Ethereum', price: 2341.87, change: 45.23, change_pct: 1.97, volume: 12430000000 },
];

export const MOCK_REGIME = {
  current_regime: 'Strong Bullish Trend',
  confidence: 0.87,
  duration_days: 12,
  key_signals: ['SPY above 20 & 50 SMA', 'ADX > 25 rising', 'Breadth positive', 'VIX declining'],
  regime_history: [
    { date: '2026-07-15', regime: 'Ranging', confidence: 0.65 },
    { date: '2026-07-20', regime: 'Weak Bullish', confidence: 0.58 },
    { date: '2026-07-25', regime: 'Strong Bullish Trend', confidence: 0.72 },
    { date: '2026-08-01', regime: 'Strong Bullish Trend', confidence: 0.81 },
    { date: '2026-08-05', regime: 'Weak Bullish', confidence: 0.55 },
    { date: '2026-08-10', regime: 'Strong Bullish Trend', confidence: 0.87 },
  ],
};

export const MOCK_POSITIONS = [
  { symbol: 'AAPL', direction: 'LONG', size: 50, entry_price: 178.45, current_price: 182.30, stop_loss: 174.50, target: 190.00, unrealized_pnl: 192.50, pnl_pct: 2.16, strategy: 'Momentum Burst' },
  { symbol: 'MSFT', direction: 'LONG', size: 30, entry_price: 338.20, current_price: 345.67, stop_loss: 330.00, target: 360.00, unrealized_pnl: 224.10, pnl_pct: 2.21, strategy: 'Trend Following' },
  { symbol: 'TSLA', direction: 'SHORT', size: 20, entry_price: 265.80, current_price: 258.45, stop_loss: 275.00, target: 245.00, unrealized_pnl: 147.00, pnl_pct: 2.77, strategy: 'Mean Reversion' },
  { symbol: 'NVDA', direction: 'LONG', size: 15, entry_price: 487.30, current_price: 495.12, stop_loss: 475.00, target: 520.00, unrealized_pnl: 117.30, pnl_pct: 1.60, strategy: 'Breakout' },
  { symbol: 'AMD', direction: 'LONG', size: 40, entry_price: 121.50, current_price: 118.20, stop_loss: 116.00, target: 132.00, unrealized_pnl: -132.00, pnl_pct: -2.72, strategy: 'Momentum Burst' },
];

export const MOCK_SIGNALS = [
  { id: 'SIG-001', timestamp: '2026-08-14T13:45:00Z', symbol: 'AAPL', strategy: 'Momentum Burst', direction: 'LONG', score: 0.87, status: 'EXECUTED', reason: 'RSI breakout + volume surge' },
  { id: 'SIG-002', timestamp: '2026-08-14T13:30:00Z', symbol: 'GOOGL', strategy: 'Trend Following', direction: 'LONG', score: 0.72, status: 'REJECTED', reason: 'Correlated exposure limit' },
  { id: 'SIG-003', timestamp: '2026-08-14T13:15:00Z', symbol: 'TSLA', strategy: 'Mean Reversion', direction: 'SHORT', score: 0.91, status: 'EXECUTED', reason: 'Bollinger band rejection' },
  { id: 'SIG-004', timestamp: '2026-08-14T12:55:00Z', symbol: 'META', strategy: 'Breakout', direction: 'LONG', score: 0.65, status: 'EXPIRED', reason: 'Resistance breakout setup' },
  { id: 'SIG-005', timestamp: '2026-08-14T12:30:00Z', symbol: 'AMZN', strategy: 'Momentum Burst', direction: 'LONG', score: 0.78, status: 'EXECUTED', reason: 'MACD cross + trend confirm' },
  { id: 'SIG-006', timestamp: '2026-08-14T12:10:00Z', symbol: 'NFLX', strategy: 'Mean Reversion', direction: 'SHORT', score: 0.69, status: 'REJECTED', reason: 'Daily loss limit near' },
  { id: 'SIG-007', timestamp: '2026-08-14T11:45:00Z', symbol: 'MSFT', strategy: 'Trend Following', direction: 'LONG', score: 0.83, status: 'EXECUTED', reason: 'EMA cross + ADX confirm' },
  { id: 'SIG-008', timestamp: '2026-08-14T11:20:00Z', symbol: 'JPM', strategy: 'Breakout', direction: 'LONG', score: 0.55, status: 'EXPIRED', reason: 'Range breakout pending' },
  { id: 'SIG-009', timestamp: '2026-08-14T11:00:00Z', symbol: 'V', strategy: 'Momentum Burst', direction: 'LONG', score: 0.82, status: 'EXECUTED', reason: 'Relative strength leader' },
  { id: 'SIG-010', timestamp: '2026-08-14T10:30:00Z', symbol: 'COIN', strategy: 'Mean Reversion', direction: 'SHORT', score: 0.74, status: 'REJECTED', reason: 'Insufficient volume' },
];

export const MOCK_RISK = {
  risk_per_trade: { used: 1.2, max: 2.0 },
  daily_loss: { used: 0.45, max: 3.0 },
  weekly_loss: { used: 1.2, max: 6.0 },
  portfolio_drawdown: { current: 3.21, max: 15.0 },
  simultaneous_positions: { current: 5, max: 10 },
  correlated_exposure: { current: 35, max: 60 },
  circuit_breaker: { status: 'NORMAL' as const, reason: null as string | null },
  risk_events: [
    { timestamp: '2026-08-14T13:30:00Z', type: 'POSITION_LIMIT', severity: 'INFO', description: 'Correlated exposure check: GOOGL blocked (tech sector 35% exposed)' },
    { timestamp: '2026-08-14T12:10:00Z', type: 'DAILY_LOSS_WARNING', severity: 'WARNING', description: 'Daily loss approaching 50% of limit' },
    { timestamp: '2026-08-14T10:45:00Z', type: 'SLIPPAGE_ALERT', severity: 'INFO', description: 'AAPL entry slippage: 0.12% (within tolerance)' },
    { timestamp: '2026-08-13T15:55:00Z', type: 'CIRCUIT_BREAKER', severity: 'CRITICAL', description: 'Circuit breaker triggered: 3 consecutive losses in 30min' },
    { timestamp: '2026-08-13T15:56:00Z', type: 'CIRCUIT_BREAKER_RESET', severity: 'INFO', description: 'Circuit breaker reset after 15min cooling period' },
  ],
  correlation_matrix: {
    symbols: ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMD'],
    values: [
      [1.00, 0.82, 0.45, 0.71, 0.68],
      [0.82, 1.00, 0.38, 0.75, 0.62],
      [0.45, 0.38, 1.00, 0.52, 0.49],
      [0.71, 0.75, 0.52, 1.00, 0.85],
      [0.68, 0.62, 0.49, 0.85, 1.00],
    ],
  },
};

export const MOCK_STRATEGIES = [
  { id: 'STR-001', name: 'Momentum Burst', version: '2.3.1', status: 'ACTIVE', win_rate: 62.5, expectancy: 1.45, profit_factor: 1.87, sharpe: 1.92, max_dd: -8.3, total_trades: 234, last_trade: '2026-08-14T13:45:00Z', allocation_pct: 30, type: 'Momentum' },
  { id: 'STR-002', name: 'Trend Following', version: '3.1.0', status: 'ACTIVE', win_rate: 55.8, expectancy: 2.12, profit_factor: 2.34, sharpe: 2.15, max_dd: -6.1, total_trades: 156, last_trade: '2026-08-14T13:30:00Z', allocation_pct: 25, type: 'Trend' },
  { id: 'STR-003', name: 'Mean Reversion', version: '1.8.2', status: 'ACTIVE', win_rate: 68.2, expectancy: 0.89, profit_factor: 1.62, sharpe: 1.45, max_dd: -5.7, total_trades: 312, last_trade: '2026-08-14T13:15:00Z', allocation_pct: 20, type: 'Mean Reversion' },
  { id: 'STR-004', name: 'Breakout Alpha', version: '1.2.0', status: 'WATCH', win_rate: 48.3, expectancy: 1.78, profit_factor: 1.53, sharpe: 1.12, max_dd: -11.2, total_trades: 89, last_trade: '2026-08-14T12:55:00Z', allocation_pct: 15, type: 'Breakout' },
  { id: 'STR-005', name: 'Volatility Scalper', version: '0.9.1', status: 'DEGRADED', win_rate: 71.4, expectancy: 0.34, profit_factor: 1.21, sharpe: 0.78, max_dd: -4.5, total_trades: 567, last_trade: '2026-08-13T15:30:00Z', allocation_pct: 10, type: 'Momentum' },
  { id: 'STR-006', name: 'Gap Fill Pro', version: '2.0.0', status: 'SUSPENDED', win_rate: 42.1, expectancy: -0.23, profit_factor: 0.87, sharpe: -0.34, max_dd: -15.8, total_trades: 178, last_trade: '2026-08-10T09:45:00Z', allocation_pct: 0, type: 'Mean Reversion' },
  { id: 'STR-007', name: 'Sector Rotation', version: '1.0.0', status: 'RETIRED', win_rate: 51.2, expectancy: 0.56, profit_factor: 1.15, sharpe: 0.65, max_dd: -12.3, total_trades: 345, last_trade: '2026-07-15T14:00:00Z', allocation_pct: 0, type: 'Trend' },
];

export const MOCK_STRATEGY_PIPELINE = [
  { name: 'Neural Pattern v1', stage: 'RESEARCH', days_in_stage: 3 },
  { name: 'Crypto Momentum', stage: 'HYPOTHESIS', days_in_stage: 7 },
  { name: 'Pair Trading ETF', stage: 'BACKTEST', days_in_stage: 2 },
  { name: 'Earnings Drift', stage: 'OUT-OF-SAMPLE', days_in_stage: 5 },
  { name: 'IV Crush Play', stage: 'WALK-FORWARD', days_in_stage: 14 },
  { name: 'Overnight Momentum', stage: 'MONTE CARLO', days_in_stage: 3 },
  { name: 'RSI Divergence', stage: 'PAPER', days_in_stage: 21 },
  { name: 'Momentum Burst v2.4', stage: 'SHADOW', days_in_stage: 10 },
];

export const MOCK_HYPOTHESES = [
  { id: 'HYP-2026-000142', title: 'RSI Divergence in high-ADX environments yields 2:1 RR', status: 'TESTING', confidence: 0.72, created: '2026-08-10', assets: ['SPY', 'QQQ'], timeframe: '1H', regime: 'Trending' },
  { id: 'HYP-2026-000141', title: 'VWAP bounce with volume confirm > 65% win rate', status: 'PASSED', confidence: 0.85, created: '2026-08-08', assets: ['AAPL', 'MSFT', 'NVDA'], timeframe: '15M', regime: 'All' },
  { id: 'HYP-2026-000140', title: 'Mean reversion on 3-sigma deviation in ranging markets', status: 'PASSED', confidence: 0.78, created: '2026-08-05', assets: ['All Large Cap'], timeframe: '4H', regime: 'Ranging' },
  { id: 'HYP-2026-000139', title: 'Gap fills complete 80% within 2 sessions', status: 'FAILED', confidence: 0.42, created: '2026-08-03', assets: ['All'], timeframe: '1D', regime: 'All' },
  { id: 'HYP-2026-000138', title: 'Crypto momentum after BTC breakout persists 3+ days', status: 'TESTING', confidence: 0.63, created: '2026-08-01', assets: ['BTC/USD', 'ETH/USD'], timeframe: '4H', regime: 'Bullish' },
  { id: 'HYP-2026-000137', title: 'Sector rotation signal precedes SPY moves by 2 days', status: 'FAILED', confidence: 0.31, created: '2026-07-28', assets: ['XLK', 'XLF', 'XLE'], timeframe: '1D', regime: 'All' },
];

export const MOCK_BACKTESTS = [
  { strategy: 'RSI Divergence v1', date: '2026-08-12', sharpe: 1.67, max_dd: -7.8, win_rate: 61.3, status: 'PASSED' },
  { strategy: 'VWAP Bounce v2', date: '2026-08-10', sharpe: 1.92, max_dd: -5.2, win_rate: 66.7, status: 'PASSED' },
  { strategy: 'Gap Fill Pro v3', date: '2026-08-08', sharpe: 0.45, max_dd: -18.3, win_rate: 42.1, status: 'OVERFITTING' },
  { strategy: 'Crypto Momentum v1', date: '2026-08-06', sharpe: -0.12, max_dd: -22.5, win_rate: 38.9, status: 'FAILED' },
  { strategy: 'Mean Reversion v2', date: '2026-08-04', sharpe: 1.45, max_dd: -6.1, win_rate: 68.2, status: 'PASSED' },
];

export const MOCK_KNOWLEDGE_FEED = [
  { timestamp: '2026-08-14T14:00:00Z', entry: 'Momentum strategies perform 23% better when VIX < 18 and ADX > 30', source: 'Backtest Analysis' },
  { timestamp: '2026-08-14T12:00:00Z', entry: 'NVDA-AMD correlation increased to 0.85 — adjust correlated exposure limits', source: 'Correlation Monitor' },
  { timestamp: '2026-08-13T16:00:00Z', entry: 'Mean reversion win rate drops to 45% in strong trend regimes — add regime filter', source: 'Strategy Audit' },
  { timestamp: '2026-08-13T10:00:00Z', entry: 'Optimal position size for current volatility: 1.2% risk per trade', source: 'Kelly Calculator' },
];

export const MOCK_NEWS = [
  { timestamp: '2026-08-14T14:30:00Z', headline: 'Fed signals potential rate pause at September meeting', sentiment: 'BULLISH', assets: ['SPY', 'QQQ', 'TLT'], relevance: 0.95, source: 'Reuters' },
  { timestamp: '2026-08-14T13:00:00Z', headline: 'NVIDIA beats earnings expectations, raises guidance', sentiment: 'BULLISH', assets: ['NVDA', 'AMD', 'SMH'], relevance: 0.92, source: 'Bloomberg' },
  { timestamp: '2026-08-14T11:30:00Z', headline: 'China exports decline for third consecutive month', sentiment: 'BEARISH', assets: ['FXI', 'EEM', 'BABA'], relevance: 0.78, source: 'CNBC' },
  { timestamp: '2026-08-14T10:00:00Z', headline: 'Bitcoin ETF sees record inflows amid institutional adoption', sentiment: 'BULLISH', assets: ['BTC/USD', 'COIN', 'MARA'], relevance: 0.85, source: 'CoinDesk' },
  { timestamp: '2026-08-14T08:30:00Z', headline: 'US CPI comes in below expectations at 2.8% YoY', sentiment: 'BULLISH', assets: ['SPY', 'TLT', 'GLD'], relevance: 0.98, source: 'BLS' },
];

export const MOCK_CALENDAR = [
  { date: '2026-08-15T08:30:00Z', event: 'Retail Sales MoM', impact: 'HIGH', expected: '0.3%', previous: '0.1%', actual: null },
  { date: '2026-08-15T10:00:00Z', event: 'Michigan Consumer Sentiment', impact: 'MEDIUM', expected: '72.5', previous: '71.6', actual: null },
  { date: '2026-08-18T14:00:00Z', event: 'FOMC Meeting Minutes', impact: 'EXTREME', expected: null, previous: null, actual: null },
  { date: '2026-08-20T08:30:00Z', event: 'Initial Jobless Claims', impact: 'MEDIUM', expected: '215K', previous: '218K', actual: null },
  { date: '2026-08-21T09:45:00Z', event: 'S&P Global PMI Flash', impact: 'HIGH', expected: '52.1', previous: '51.8', actual: null },
];

export const MOCK_VOLATILITY = {
  vix: 16.42,
  vix_change: -0.83,
  hist_vol_30d: 14.8,
  vol_percentile: 32,
  iv_rank: 28,
};

export const MOCK_TRADES = [
  { id: 'T-001', date: '2026-08-14', symbol: 'AAPL', strategy: 'Momentum Burst', direction: 'LONG', entry: 178.45, exit: 182.30, pnl: 192.50, pnl_pct: 2.16, mae: -0.82, mfe: 3.12, regime: 'Strong Bullish', slippage: 0.05 },
  { id: 'T-002', date: '2026-08-14', symbol: 'TSLA', strategy: 'Mean Reversion', direction: 'SHORT', entry: 265.80, exit: 258.45, pnl: 147.00, pnl_pct: 2.77, mae: -1.23, mfe: 3.45, regime: 'Strong Bullish', slippage: 0.08 },
  { id: 'T-003', date: '2026-08-13', symbol: 'NVDA', strategy: 'Breakout', direction: 'LONG', entry: 480.20, exit: 487.30, pnl: 106.50, pnl_pct: 1.48, mae: -0.45, mfe: 2.10, regime: 'Weak Bullish', slippage: 0.12 },
  { id: 'T-004', date: '2026-08-13', symbol: 'META', strategy: 'Momentum Burst', direction: 'LONG', entry: 312.50, exit: 308.20, pnl: -86.00, pnl_pct: -1.38, mae: -2.45, mfe: 0.65, regime: 'Weak Bullish', slippage: 0.04 },
  { id: 'T-005', date: '2026-08-12', symbol: 'MSFT', strategy: 'Trend Following', direction: 'LONG', entry: 332.10, exit: 338.20, pnl: 183.00, pnl_pct: 1.84, mae: -0.62, mfe: 2.30, regime: 'Strong Bullish', slippage: 0.06 },
  { id: 'T-006', date: '2026-08-12', symbol: 'AMZN', strategy: 'Momentum Burst', direction: 'LONG', entry: 142.30, exit: 145.80, pnl: 175.00, pnl_pct: 2.46, mae: -0.35, mfe: 3.00, regime: 'Strong Bullish', slippage: 0.03 },
  { id: 'T-007', date: '2026-08-11', symbol: 'AMD', strategy: 'Breakout', direction: 'LONG', entry: 118.90, exit: 115.20, pnl: -148.00, pnl_pct: -3.11, mae: -4.20, mfe: 0.40, regime: 'Ranging', slippage: 0.15 },
  { id: 'T-008', date: '2026-08-11', symbol: 'V', strategy: 'Trend Following', direction: 'LONG', entry: 267.40, exit: 272.80, pnl: 162.00, pnl_pct: 2.02, mae: -0.55, mfe: 2.50, regime: 'Strong Bullish', slippage: 0.04 },
  { id: 'T-009', date: '2026-08-10', symbol: 'GOOGL', strategy: 'Momentum Burst', direction: 'LONG', entry: 138.60, exit: 141.20, pnl: 130.00, pnl_pct: 1.88, mae: -0.72, mfe: 2.30, regime: 'Weak Bullish', slippage: 0.07 },
  { id: 'T-010', date: '2026-08-10', symbol: 'JPM', strategy: 'Breakout', direction: 'LONG', entry: 156.30, exit: 153.80, pnl: -75.00, pnl_pct: -1.60, mae: -2.80, mfe: 0.50, regime: 'Ranging', slippage: 0.09 },
];

export const MOCK_EQUITY_CURVE = Array.from({ length: 60 }, (_, i) => {
  const base = 100000;
  const growth = base * (1 + (i * 0.005) + Math.sin(i * 0.3) * 0.01);
  return { day: i + 1, date: `2026-${String(6 + Math.floor(i / 30) + 1).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}`, equity: Math.round(growth * 100) / 100 };
});

export const MOCK_MONTHLY_RETURNS = [
  { month: 'Jan', returns: 3.2 }, { month: 'Feb', returns: -1.5 },
  { month: 'Mar', returns: 4.8 }, { month: 'Apr', returns: 2.1 },
  { month: 'May', returns: -0.8 }, { month: 'Jun', returns: 5.6 },
  { month: 'Jul', returns: 7.4 }, { month: 'Aug', returns: 2.8 },
];

export const MOCK_SYSTEM_LOGS = [
  { timestamp: '2026-08-14T14:00:00Z', level: 'INFO', message: 'Market data feed connected - Alpaca WS', source: 'DataManager' },
  { timestamp: '2026-08-14T13:45:00Z', level: 'INFO', message: 'Signal SIG-001 executed: AAPL LONG @ 178.45', source: 'ExecutionEngine' },
  { timestamp: '2026-08-14T13:30:00Z', level: 'WARNING', message: 'Signal SIG-002 rejected: correlated exposure limit reached', source: 'RiskManager' },
  { timestamp: '2026-08-14T13:15:00Z', level: 'INFO', message: 'Signal SIG-003 executed: TSLA SHORT @ 265.80', source: 'ExecutionEngine' },
  { timestamp: '2026-08-14T12:55:00Z', level: 'WARNING', message: 'Signal SIG-004 expired: META breakout setup timed out', source: 'SignalProcessor' },
  { timestamp: '2026-08-14T12:00:00Z', level: 'ERROR', message: 'WebSocket reconnection attempt 3/5 — partial data gap 11:58-12:00', source: 'DataManager' },
  { timestamp: '2026-08-14T11:58:00Z', level: 'ERROR', message: 'WebSocket connection lost — attempting reconnect', source: 'DataManager' },
  { timestamp: '2026-08-14T09:30:00Z', level: 'INFO', message: 'Market opened — all strategies activated', source: 'SystemController' },
  { timestamp: '2026-08-14T09:25:00Z', level: 'INFO', message: 'Pre-market scan complete: 12 candidates identified', source: 'Scanner' },
  { timestamp: '2026-08-14T09:00:00Z', level: 'INFO', message: 'System startup — mode: PAPER, health: HEALTHY', source: 'SystemController' },
];

export const MOCK_MODE_TRANSITIONS = {
  current: 'PAPER',
  valid_transitions: ['SHADOW', 'EMERGENCY_STOP'],
  history: [
    { from: 'SHADOW', to: 'PAPER', timestamp: '2026-08-10T09:00:00Z', reason: 'Strategy degradation detected' },
    { from: 'PAPER', to: 'SHADOW', timestamp: '2026-08-05T09:00:00Z', reason: 'Promoted after 30-day paper period' },
    { from: 'EMERGENCY_STOP', to: 'PAPER', timestamp: '2026-07-20T14:00:00Z', reason: 'Circuit breaker reset — resumed in PAPER' },
  ],
};

export const MOCK_CONFIG = {
  risk_per_trade: 2.0,
  daily_loss_limit: 3.0,
  weekly_loss_limit: 6.0,
  max_drawdown: 15.0,
  max_positions: 10,
  max_correlated_exposure: 60,
  min_signal_score: 0.60,
  signal_expiry_minutes: 15,
  cooldown_minutes: 5,
};
