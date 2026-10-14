// Default production backend hosted on Render
const DEFAULT_PROD_BACKEND = 'https://money-maker-cgp2.onrender.com';

// In development, empty string uses the Vite dev proxy configured in vite.config.js (http://127.0.0.1:8000)
// In production (Netlify), defaults to the live Render backend if VITE_BACKEND_URL is not explicitly set
const RAW_BACKEND = (
  import.meta.env.VITE_BACKEND_URL || 
  (import.meta.env.DEV ? '' : DEFAULT_PROD_BACKEND)
).replace(/\/+$/, '');

// API base URL — falls back to local Vite dev proxy if not provided
const BASE_URL = RAW_BACKEND ? `${RAW_BACKEND}/api` : '/api';

// WebSocket URL: uses wss:// on Render in production, ws:// in local dev
const WS_URL = RAW_BACKEND
  ? `${RAW_BACKEND.replace(/^http/, 'ws')}/ws`
  : `${typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'}://${typeof window !== 'undefined' ? window.location.host : 'localhost:8000'}/ws`;

export { WS_URL, BASE_URL };

export async function fetchOverview() {
  const res = await fetch(`${BASE_URL}/overview`);
  if (!res.ok) throw new Error(`Overview fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchScanner(filters = {}) {
  const params = new URLSearchParams();
  if (filters.sector) params.append('sector', filters.sector);
  if (filters.setup_type) params.append('setup_type', filters.setup_type);
  if (filters.min_liquidity) params.append('min_liquidity', filters.min_liquidity);
  if (filters.watchlist_only) params.append('watchlist_only', 'true');
  if (filters.search) params.append('search', filters.search);

  const res = await fetch(`${BASE_URL}/scanner?${params.toString()}`);
  if (!res.ok) throw new Error(`Scanner fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchStockAnalysis(symbol) {
  const res = await fetch(`${BASE_URL}/analysis/${symbol}`);
  if (!res.ok) throw new Error(`Stock analysis fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchSignals(status = null) {
  const url = status ? `${BASE_URL}/signals?status=${status}` : `${BASE_URL}/signals`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Signals fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchAlerts(unreadOnly = false) {
  const res = await fetch(`${BASE_URL}/alerts?unread_only=${unreadOnly}`);
  if (!res.ok) throw new Error(`Alerts fetch failed: ${res.statusText}`);
  return res.json();
}

export async function dismissAlert(alertId) {
  const res = await fetch(`${BASE_URL}/alerts/${alertId}/dismiss`, { method: 'POST' });
  return res.json();
}

export async function calculateRisk(payload) {
  const res = await fetch(`${BASE_URL}/risk/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Risk calculation failed: ${res.statusText}`);
  return res.json();
}

export async function fetchNews(symbol = null, sector = null) {
  const params = new URLSearchParams();
  if (symbol) params.append('symbol', symbol);
  if (sector) params.append('sector', sector);
  const res = await fetch(`${BASE_URL}/news?${params.toString()}`);
  if (!res.ok) throw new Error(`News fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchModelPerformance() {
  const res = await fetch(`${BASE_URL}/ml/performance`);
  if (!res.ok) throw new Error(`ML performance fetch failed: ${res.statusText}`);
  return res.json();
}

export async function runBacktest(payload = {}) {
  const params = new URLSearchParams();
  if (payload.initial_capital) params.append('initial_capital', payload.initial_capital);
  if (payload.risk_pct) params.append('risk_pct', payload.risk_pct);
  if (payload.slippage_bps) params.append('slippage_bps', payload.slippage_bps);

  const res = await fetch(`${BASE_URL}/ml/backtest?${params.toString()}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Backtest run failed: ${res.statusText}`);
  return res.json();
}

export async function fetchJournal() {
  const res = await fetch(`${BASE_URL}/journal`);
  if (!res.ok) throw new Error(`Journal fetch failed: ${res.statusText}`);
  return res.json();
}

export async function addJournalEntry(payload) {
  const res = await fetch(`${BASE_URL}/journal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Journal add failed: ${res.statusText}`);
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch(`${BASE_URL}/settings`);
  if (!res.ok) throw new Error(`Settings fetch failed: ${res.statusText}`);
  return res.json();
}

export async function updateProviderSettings(payload) {
  const res = await fetch(`${BASE_URL}/settings/provider`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return res.json();
}

export async function toggleWatchlist(symbol) {
  const res = await fetch(`${BASE_URL}/watchlist/toggle?symbol=${symbol}`, { method: 'POST' });
  return res.json();
}

export async function testConnectionHealth() {
  try {
    const healthUrl = RAW_BACKEND ? `${RAW_BACKEND}/health` : '/health';
    const res = await fetch(healthUrl);
    if (!res.ok) return { online: false };
    const data = await res.json();
    return { online: true, ...data };
  } catch {
    return { online: false };
  }
}

export async function fetchRecommendations(limit = 5) {
  const res = await fetch(`${BASE_URL}/recommendations?limit=${limit}`);
  if (!res.ok) throw new Error(`Recommendations fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchTelegramStatus() {
  const res = await fetch(`${BASE_URL}/telegram/status`);
  if (!res.ok) throw new Error(`Telegram status fetch failed: ${res.statusText}`);
  return res.json();
}

export async function updateTelegramConfig(config) {
  const res = await fetch(`${BASE_URL}/telegram/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  if (!res.ok) throw new Error(`Telegram config update failed: ${res.statusText}`);
  return res.json();
}

export async function sendTestTelegramAlert() {
  const res = await fetch(`${BASE_URL}/telegram/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) throw new Error(`Test alert failed: ${res.statusText}`);
  return res.json();
}

export async function broadcastPicksToTelegram(limit = 3) {
  const res = await fetch(`${BASE_URL}/telegram/broadcast-picks?limit=${limit}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Broadcast failed: ${res.statusText}`);
  return res.json();
}

export async function fetchMlStatus() {
  const res = await fetch(`${BASE_URL}/ml/status`);
  if (!res.ok) throw new Error(`ML status fetch failed: ${res.statusText}`);
  return res.json();
}

export async function retrainMlModel() {
  const res = await fetch(`${BASE_URL}/ml/retrain`, { method: 'POST' });
  if (!res.ok) throw new Error(`Model retrain failed: ${res.statusText}`);
  return res.json();
}

export async function fetchDeliveryRecommendations(options = {}) {
  const params = new URLSearchParams();
  if (options.budget) params.append('budget', options.budget);
  if (options.horizon) params.append('horizon', options.horizon);
  if (options.max_price) params.append('max_price', options.max_price);
  if (options.risk_profile) params.append('risk_profile', options.risk_profile);
  if (options.limit) params.append('limit', options.limit);

  const res = await fetch(`${BASE_URL}/delivery/recommendations?${params.toString()}`);
  if (!res.ok) throw new Error(`Delivery recommendations fetch failed: ${res.statusText}`);
  return res.json();
}

export async function broadcastDeliveryToTelegram(payload = {}) {
  const res = await fetch(`${BASE_URL}/delivery/broadcast-telegram`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`Delivery broadcast failed: ${res.statusText}`);
  return res.json();
}

// --- Paper Trading Simulator APIs ---
export async function fetchPaperPortfolio() {
  const res = await fetch(`${BASE_URL}/paper/portfolio`);
  if (!res.ok) throw new Error(`Paper portfolio fetch failed: ${res.statusText}`);
  return res.json();
}

export async function placePaperTrade(tradePayload) {
  const res = await fetch(`${BASE_URL}/paper/place-trade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tradePayload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Paper order failed: ${res.statusText}`);
  }
  return res.json();
}

export async function closePaperPosition(positionId) {
  const res = await fetch(`${BASE_URL}/paper/close-position?position_id=${positionId}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Close position failed: ${res.statusText}`);
  return res.json();
}

export async function resetPaperPortfolio(initialCash = 10000) {
  const res = await fetch(`${BASE_URL}/paper/reset?initial_cash=${initialCash}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Portfolio reset failed: ${res.statusText}`);
  return res.json();
}

// --- Recommendations History API ---
export async function fetchRecommendationsHistory(tradeType = 'ALL', limit = 100) {
  const res = await fetch(`${BASE_URL}/recommendations/history?trade_type=${tradeType}&limit=${limit}`);
  if (!res.ok) throw new Error(`History fetch failed: ${res.statusText}`);
  return res.json();
}

// --- Paper Trading History API ---
export async function fetchPaperTradingHistory(limit = 100) {
  const res = await fetch(`${BASE_URL}/paper/history?limit=${limit}`);
  if (!res.ok) throw new Error(`Paper history fetch failed: ${res.statusText}`);
  return res.json();
}

// --- AI Auto-Trader APIs ---
export async function fetchAiTraderStatus() {
  const res = await fetch(`${BASE_URL}/ai-trader/status`);
  if (!res.ok) throw new Error(`AI Trader status fetch failed: ${res.statusText}`);
  return res.json();
}

export async function toggleAiTrader(payload) {
  const res = await fetch(`${BASE_URL}/ai-trader/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`AI Trader toggle failed: ${res.statusText}`);
  return res.json();
}

export async function triggerAiTraderScan() {
  const res = await fetch(`${BASE_URL}/ai-trader/scan-now`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Scan trigger failed: ${res.statusText}`);
  return res.json();
}

export async function fetchAiTradesHistory(limit = 100) {
  const res = await fetch(`${BASE_URL}/ai-trader/history?limit=${limit}`);
  if (!res.ok) throw new Error(`AI Trades history fetch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchAiTradesAccuracy() {
  const res = await fetch(`${BASE_URL}/ai-trader/accuracy`);
  if (!res.ok) throw new Error(`AI Trades accuracy fetch failed: ${res.statusText}`);
  return res.json();
}

export async function retrainFromAiTrades() {
  const res = await fetch(`${BASE_URL}/ai-trader/train-from-trades`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`Train from trades failed: ${res.statusText}`);
  return res.json();
}



