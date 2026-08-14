// Unified API client with mock data fallback

import * as MockData from './mock-data';

// All API calls go through our own proxy route to avoid browser CORS/connection errors
export async function fetchApi<T>(endpoint: string, mockData: T, options?: RequestInit): Promise<{ data: T; isMock: boolean }> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`/api/proxy?endpoint=${encodeURIComponent(endpoint)}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers ?? {}),
      },
    });
    clearTimeout(timeoutId);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const json = await res.json();
    if (json?._mock) return { data: mockData, isMock: true };
    return { data: json as T, isMock: false };
  } catch {
    return { data: mockData, isMock: true };
  }
}

// Convenience fetchers for each data domain
export const api = {
  getSystemStatus: () => fetchApi('/api/system/status', MockData.MOCK_SYSTEM_STATUS),
  getAccount: () => fetchApi('/api/account', MockData.MOCK_ACCOUNT),
  getMarketOverview: () => fetchApi('/api/market/overview', MockData.MOCK_MARKET_OVERVIEW),
  getRegime: () => fetchApi('/api/market/regime', MockData.MOCK_REGIME),
  getPositions: () => fetchApi('/api/positions', MockData.MOCK_POSITIONS),
  getSignals: () => fetchApi('/api/signals/recent', MockData.MOCK_SIGNALS),
  getRisk: () => fetchApi('/api/risk', MockData.MOCK_RISK),
  getStrategies: () => fetchApi('/api/strategies', MockData.MOCK_STRATEGIES),
  getStrategyPipeline: () => fetchApi('/api/strategies/pipeline', MockData.MOCK_STRATEGY_PIPELINE),
  getHypotheses: () => fetchApi('/api/research/hypotheses', MockData.MOCK_HYPOTHESES),
  getBacktests: () => fetchApi('/api/research/backtests', MockData.MOCK_BACKTESTS),
  getKnowledge: () => fetchApi('/api/research/knowledge', MockData.MOCK_KNOWLEDGE_FEED),
  getNews: () => fetchApi('/api/market/news', MockData.MOCK_NEWS),
  getCalendar: () => fetchApi('/api/market/calendar', MockData.MOCK_CALENDAR),
  getVolatility: () => fetchApi('/api/market/volatility', MockData.MOCK_VOLATILITY),
  getTrades: () => fetchApi('/api/trades', MockData.MOCK_TRADES),
  getEquityCurve: () => fetchApi('/api/performance/equity', MockData.MOCK_EQUITY_CURVE),
  getMonthlyReturns: () => fetchApi('/api/performance/monthly', MockData.MOCK_MONTHLY_RETURNS),
  getSystemLogs: () => fetchApi('/api/system/logs', MockData.MOCK_SYSTEM_LOGS),
  getModeTransitions: () => fetchApi('/api/system/mode', MockData.MOCK_MODE_TRANSITIONS),
  getConfig: () => fetchApi('/api/system/config', MockData.MOCK_CONFIG),
  killSwitch: () => fetchApi('/api/system/kill', null, { method: 'POST' }),
  transitionMode: (mode: string) => fetchApi('/api/system/mode/transition', null, { method: 'POST', body: JSON.stringify({ target_mode: mode }) }),
};
