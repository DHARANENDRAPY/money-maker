import React, { useState, useEffect, useCallback } from 'react';
import { 
  History, 
  Target, 
  PackageCheck, 
  ArrowUpRight, 
  ArrowDownRight, 
  Clock, 
  Calendar, 
  ShieldAlert, 
  RefreshCw, 
  Send, 
  CheckCircle2, 
  Percent,
  Search,
  Layers,
  Sparkles,
  Wallet,
  CheckCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  RotateCcw
} from 'lucide-react';
import { 
  fetchRecommendationsHistory, 
  fetchPaperTradingHistory, 
  fetchAiTradesHistory, 
  fetchAiTradesAccuracy,
  retrainFromAiTrades,
  resetPaperPortfolio
} from '../../services/api';
import { useMarket } from '../../context/MarketContext';
import { Bot } from 'lucide-react';

export default function HistoryPage() {
  const { showToast } = useMarket();
  const [tradeType, setTradeType] = useState('ALL'); // ALL, INTRADAY, DELIVERY, PAPER, AI_BOT
  const [searchTerm, setSearchTerm] = useState('');
  const [historyData, setHistoryData] = useState([]);
  const [paperHistoryData, setPaperHistoryData] = useState([]);
  const [paperStats, setPaperStats] = useState({ win_rate: 0, open_count: 0, closed_count: 0 });
  const [aiHistoryData, setAiHistoryData] = useState([]);
  const [aiAccuracy, setAiAccuracy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleResetAllHistory = async () => {
    if (!window.confirm("Are you sure you want to purge all old historical recommendations and paper trading records to start fresh with the new institutional prediction technique?")) {
      return;
    }
    try {
      setIsResetting(true);
      await resetPaperPortfolio(10000000);
      showToast?.("All old records purged. Starting fresh with new prediction models!", "success");
      await loadHistory(false);
    } catch (err) {
      showToast?.("Failed to purge records: " + err.message, "error");
    } finally {
      setIsResetting(false);
    }
  };

  const loadHistory = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) {
        setIsRefreshing(true);
        setErrorMessage(null);
      }
      if (tradeType === 'PAPER') {
        const res = await fetchPaperTradingHistory(100);
        setPaperHistoryData(res?.history || []);
        setPaperStats({
          win_rate: res?.win_rate || 0,
          open_count: res?.open_count || 0,
          closed_count: res?.closed_count || 0
        });
      } else if (tradeType === 'AI_BOT') {
        const [hRes, aRes] = await Promise.allSettled([
          fetchAiTradesHistory(100),
          fetchAiTradesAccuracy()
        ]);
        if (hRes.status === 'fulfilled') {
          setAiHistoryData(hRes.value?.history || []);
        } else {
          setAiHistoryData([]);
        }
        if (aRes.status === 'fulfilled') {
          setAiAccuracy(aRes.value || null);
        }
      } else {
        const res = await fetchRecommendationsHistory(tradeType, 100);
        setHistoryData(res?.history || []);
      }
    } catch (err) {
      console.warn('History load error:', err);
      // Don't pop up disruptive error toasts on background silent polling
      if (!isSilent) {
        setErrorMessage(err.message || 'Failed to load records. Retrying...');
      }
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [tradeType]);

  useEffect(() => {
    loadHistory(false);
    // Poll updates every 25 seconds
    const interval = setInterval(() => loadHistory(true), 25000);
    return () => clearInterval(interval);
  }, [loadHistory]);

  const isPaperView = tradeType === 'PAPER';
  const isAiView = tradeType === 'AI_BOT';

  const getSourceData = () => {
    if (isAiView) return aiHistoryData;
    if (isPaperView) return paperHistoryData;
    return historyData;
  };

  const filteredHistory = (getSourceData() || []).filter((item) => {
    if (!item) return false;
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      (item.symbol && item.symbol.toLowerCase().includes(term)) ||
      (item.name && item.name.toLowerCase().includes(term)) ||
      (item.strategy && item.strategy.toLowerCase().includes(term))
    );
  });

  const formatDate = (isoStr) => {
    if (!isoStr) return '--';
    try {
      let s = String(isoStr).trim();
      // If the ISO string doesn't have a timezone specifier ('Z' or +HH:MM / -HH:MM),
      // append 'Z' so JavaScript treats it as UTC, avoiding local-time misinterpretation
      if (!s.endsWith('Z') && !s.includes('+') && !/[-+]\d{2}:\d{2}$/.test(s)) {
        s = s.replace(' ', 'T') + 'Z';
      }
      const d = new Date(s);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 rounded-2xl p-5 md:p-6 border border-indigo-500/30 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-semibold flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-cyan-400" />
                CENTRAL RECOMMENDATION VAULT
              </span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 text-[11px] font-mono font-bold">
                AUTO-SAVED & TELEGRAM LOGGED
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              All Suggested Stocks <span className="text-cyan-400">History Log</span>
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-1 max-w-2xl">
              Complete chronological audit trail of all Intraday and Delivery stocks suggested by the system — with exact date, time, entry price, targets, stop-loss, holding time, and reason.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => loadHistory(false)}
              disabled={isRefreshing}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
              <span>Refresh Log</span>
            </button>
            <button
              onClick={handleResetAllHistory}
              disabled={isResetting}
              className="px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-semibold border border-rose-500/30 flex items-center gap-1.5 transition-all"
              title="Clears all old trade logs and recommendations to start fresh with new predictions"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
              <span>{isResetting ? 'Purging...' : 'Purge Old Data & Start Fresh'}</span>
            </button>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mt-5 pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: 'ALL', label: 'All Recommendations', icon: Layers },
              { id: 'INTRADAY', label: 'Intraday Picks', icon: Target },
              { id: 'DELIVERY', label: 'Delivery / Swing', icon: PackageCheck },
              { id: 'PAPER', label: 'Paper Trading Ledger', icon: Wallet, highlight: true },
              { id: 'AI_BOT', label: 'AI Auto-Trades (5m)', icon: Bot, isAi: true }
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = tradeType === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setTradeType(tab.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                    isActive
                      ? tab.isAi
                        ? 'bg-purple-500 text-white font-bold shadow-md shadow-purple-500/30'
                        : tab.highlight
                          ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                          : 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
                      : tab.isAi
                        ? 'bg-purple-950/40 text-purple-300 hover:bg-purple-900/40 border border-purple-500/40 font-semibold'
                        : tab.highlight
                          ? 'bg-emerald-950/40 text-emerald-300 hover:bg-emerald-900/40 border border-emerald-500/40 font-semibold'
                          : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80 border border-slate-700/60'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search symbol, strategy..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full sm:w-64 pl-8 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-mono"
            />
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 flex items-center justify-between text-xs text-rose-300 font-mono">
          <span>⚠️ {errorMessage}</span>
          <button
            onClick={() => loadHistory(false)}
            className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 font-semibold"
          >
            Retry Now
          </button>
        </div>
      )}

      {/* Main Table / Cards */}
      {loading && filteredHistory.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Loading history records...</p>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-slate-800 space-y-2">
          <History className="w-8 h-8 text-slate-500 mx-auto" />
          <p className="text-sm font-semibold text-slate-300">
            {isAiView 
              ? 'No AI automated transactions recorded yet' 
              : isPaperView 
                ? 'No paper trades recorded yet' 
                : 'No recommendations recorded yet'}
          </p>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {isAiView
              ? 'When the 5-minute AI Auto-Trader executes high-probability trades (>50% win rate), transactions will automatically appear here with ML scores and outcome tracking.'
              : 'Stocks suggested in Intraday or Delivery will automatically be stored here with full audit metrics and Telegram logs.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-slate-400 font-mono px-1 flex items-center justify-between">
            <span>Showing {filteredHistory.length} Recorded Transactions</span>
            <span>All times in IST</span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {isAiView ? (
              filteredHistory.map((item) => {
                const isClosed = item.status !== 'OPEN';
                const isWin = (item.net_pnl || 0) > 0;
                const pnl = item.net_pnl || 0;
                const charges = item.total_charges || 0;
                const isLong = item.direction === 'LONG';
                const mlProbPct = item.ml_probability ? Math.round(item.ml_probability * 100) : 0;

                return (
                  <div
                    key={item.trade_id || item.id}
                    className="bg-slate-900/90 rounded-xl border border-purple-900/40 hover:border-purple-500/40 p-4 transition-all shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    {/* Left: Identity & Badges */}
                    <div className="space-y-1.5 md:w-1/4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-base text-white">{item.symbol}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold ${
                          isClosed
                            ? isWin
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                            : 'bg-purple-500/20 text-purple-300 border border-purple-500/40 animate-pulse'
                        }`}>
                          {item.status}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                          isLong ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {item.direction}
                        </span>
                      </div>

                      <div className="text-xs text-purple-300 font-sans flex items-center gap-1.5">
                        <Bot className="w-3.5 h-3.5 text-purple-400" />
                        <span>AI Auto-Trade · {item.quantity} Qty · {item.strategy || 'High-Prob Intraday'}</span>
                      </div>

                      <div className="text-[11px] text-slate-500 font-mono space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>Entered: {formatDate(item.entry_time)}</span>
                        </div>
                        {isClosed && item.exit_time && (
                          <div className="flex items-center gap-1.5 text-slate-400">
                            <Clock className="w-3 h-3 text-slate-400" />
                            <span>Exited: {formatDate(item.exit_time)}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Middle: Prices & Execution Details */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 md:w-2/4 text-center font-mono">
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Entry Price</div>
                        <div className="text-xs font-bold text-white mt-0.5">₹{item.entry_price?.toFixed(2)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">
                          {isClosed ? 'Exit Price' : 'Target Price'}
                        </div>
                        <div className={`text-xs font-bold mt-0.5 ${isClosed ? 'text-cyan-300' : 'text-emerald-400'}`}>
                          {isClosed
                            ? `₹${item.exit_price?.toFixed(2)}`
                            : `₹${item.target_price?.toFixed(2)}`}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Stop Loss</div>
                        <div className="text-xs font-bold text-rose-400 mt-0.5">
                          ₹{item.stop_loss_price?.toFixed(2)}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Exit Reason</div>
                        <div className="text-xs font-bold text-slate-300 mt-0.5 truncate">
                          {item.exit_reason || 'In Position'}
                        </div>
                      </div>
                    </div>

                    {/* Right: AI Accuracy Metrics & PnL */}
                    <div className="space-y-1.5 md:w-1/4 md:text-right">
                      <div className="flex items-center md:justify-end gap-2 text-xs font-mono">
                        <span className="text-purple-300">ML Prob:</span>
                        <span className="font-bold text-emerald-400">{mlProbPct}%</span>
                        <span className="text-slate-500">| R:R {item.risk_reward_ratio?.toFixed(1) || '1.5'}</span>
                      </div>

                      {isClosed ? (
                        <div className={`text-base font-bold font-mono ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isWin ? '+' : ''}₹{pnl.toFixed(2)}
                        </div>
                      ) : (
                        <div className="text-xs font-bold font-mono text-purple-400">
                          Active 5m Trade
                        </div>
                      )}

                      <div className="flex items-center md:justify-end gap-1.5 text-[10px] font-mono text-slate-400">
                        {item.trained_in_ml ? (
                          <span className="text-cyan-400 font-semibold">🧬 Included in ML Model</span>
                        ) : (
                          <span className="text-slate-500">Pending Next Retrain Batch</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : isPaperView ? (
              filteredHistory.map((item) => {
                const isClosed = item.status === 'CLOSED';
                const isWin = (item.net_pnl || 0) > 0;
                const pnl = item.net_pnl || 0;
                const charges = item.charges || 0;
                const isLong = item.direction === 'LONG';

                return (
                  <div
                    key={item.id}
                    className="bg-slate-900/90 rounded-xl border border-slate-800 hover:border-slate-700 p-4 transition-all shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    {/* Left: Identity & Status */}
                    <div className="space-y-1.5 md:w-1/4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-base text-white">{item.symbol}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold ${
                          isClosed
                            ? isWin
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
                        }`}>
                          {isClosed ? (isWin ? '✅ WIN' : '🛑 LOSS') : '🟡 OPEN POSITION'}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                          isLong ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {item.direction}
                        </span>
                      </div>

                      <div className="text-xs text-slate-400 font-sans">
                        {item.trade_type} · {item.shares} Shares · {item.strategy}
                      </div>

                      <div className="text-[11px] text-slate-500 font-mono space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="w-3 h-3 text-slate-400" />
                          <span>Bought: {formatDate(item.bought_at_time)}</span>
                        </div>
                        {isClosed && item.sold_at_time && (
                          <div className="flex items-center gap-1.5 text-slate-400">
                            <Clock className="w-3 h-3 text-slate-400" />
                            <span>Sold: {formatDate(item.sold_at_time)}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Middle: Prices & Execution Details */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 md:w-2/4 text-center font-mono">
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Bought Price</div>
                        <div className="text-xs font-bold text-white mt-0.5">₹{item.bought_at_price?.toFixed(2)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">
                          {isClosed ? 'Sold Price' : 'Target Price'}
                        </div>
                        <div className={`text-xs font-bold mt-0.5 ${isClosed ? 'text-cyan-300' : 'text-emerald-400'}`}>
                          {isClosed
                            ? `₹${item.sold_at_price?.toFixed(2)}`
                            : `₹${item.planned_target?.toFixed(2)}`}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Brokerage & STT</div>
                        <div className="text-xs font-bold text-slate-300 mt-0.5">
                          {isClosed ? `₹${charges.toFixed(2)}` : 'At Exit'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Exit Reason</div>
                        <div className="text-xs font-bold text-slate-300 mt-0.5 truncate">
                          {item.exit_reason || '--'}
                        </div>
                      </div>
                    </div>

                    {/* Right: Realized Profit & Loss */}
                    <div className="space-y-1.5 md:w-1/4 md:text-right">
                      <div className="text-[11px] text-slate-400 font-mono">
                        {isClosed ? 'Net Realized P&L:' : 'Position Status:'}
                      </div>

                      {isClosed ? (
                        <div className={`text-base font-bold font-mono ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isWin ? '+' : ''}₹{pnl.toFixed(2)}
                        </div>
                      ) : (
                        <div className="text-xs font-bold font-mono text-amber-400">
                          Active in Market
                        </div>
                      )}

                      <div className="text-[10px] text-slate-500 font-mono">
                        {isClosed ? `Gross P&L: ₹${(item.gross_pnl || 0).toFixed(2)}` : `Stop Loss: ₹${item.planned_stop_loss?.toFixed(2)}`}
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              filteredHistory.map((item) => {
                const isIntraday = item.trade_type === 'INTRADAY';
                const isLong = item.direction === 'LONG';

                return (
                  <div
                    key={item.id}
                    className="bg-slate-900/90 rounded-xl border border-slate-800 hover:border-slate-700 p-4 transition-all shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    {/* Left: Identity & Badges */}
                    <div className="space-y-1.5 md:w-1/4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-base text-white">{item.symbol}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold ${
                          isIntraday
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40'
                        }`}>
                          {isIntraday ? '⚡ INTRADAY' : '💎 DELIVERY'}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                          isLong ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {item.direction}
                        </span>
                      </div>

                      <div className="text-xs text-slate-400 font-sans">
                        {item.name || item.symbol} · {item.sector || 'NSE Equity'}
                      </div>

                      <div className="text-[11px] text-slate-500 font-mono flex items-center gap-1.5">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span>{formatDate(item.timestamp)}</span>
                      </div>
                    </div>

                    {/* Middle: Key Trading Metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 md:w-2/4 text-center font-mono">
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase">Entry Price</div>
                        <div className="text-xs font-bold text-white mt-0.5">₹{item.entry_price?.toFixed(2)}</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-emerald-400 uppercase">Target (Exit)</div>
                        <div className="text-xs font-bold text-emerald-400 mt-0.5">
                          ₹{item.target_1?.toFixed(2)}{' '}
                          <span className="text-[10px]">
                            (+{item.expected_profit_pct?.toFixed(1)}%)
                          </span>
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-rose-400 uppercase">Stop Loss</div>
                        <div className="text-xs font-bold text-rose-400 mt-0.5">
                          ₹{item.stop_loss?.toFixed(2)}{' '}
                          <span className="text-[10px]">
                            (-{item.expected_loss_pct?.toFixed(1)}%)
                          </span>
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-cyan-400 uppercase">Hold Time</div>
                        <div className="text-xs font-bold text-cyan-300 mt-0.5 truncate">{item.holding_period}</div>
                      </div>
                    </div>

                    {/* Right: Accuracy & Rationale */}
                    <div className="space-y-1.5 md:w-1/4 md:text-right">
                      <div className="flex items-center md:justify-end gap-2 text-xs font-mono">
                        <span className="text-slate-400">Win Accuracy:</span>
                        <span className="font-bold text-emerald-400">{item.win_probability_pct}%</span>
                        <span className="text-slate-500">| R:R 1:{item.risk_reward_ratio?.toFixed(1)}</span>
                      </div>

                      <div className="text-xs text-slate-300 font-sans line-clamp-2 md:text-right">
                        <span className="text-slate-400 font-medium">Reason: </span>
                        {item.reason || item.strategy}
                      </div>

                      <div className="flex items-center md:justify-end gap-2 text-[10.5px] font-mono">
                        {item.telegram_sent ? (
                          <span className="text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Telegram Alert Sent
                          </span>
                        ) : (
                          <span className="text-slate-500">Telegram Not Sent</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
