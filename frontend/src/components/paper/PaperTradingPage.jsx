import React, { useState } from 'react';
import {
  Wallet, TrendingUp, TrendingDown, Target, ShieldAlert,
  RotateCcw, CheckCircle2, AlertTriangle, ArrowUpRight, ArrowDownRight,
  Clock, DollarSign, Award, Percent, Layers, PackageCheck, Zap
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { closePaperPosition, resetPaperPortfolio } from '../../services/api';
import AiAutoTraderPanel from './AiAutoTraderPanel';
import AiCoachPanel from './AiCoachPanel';

const renderExitReasonBadge = (reason) => {
  if (!reason) return <span className="text-slate-400">Manual Exit</span>;
  if (reason === 'TARGET_1_HIT') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">🎯 Target 1 Hit</span>;
  }
  if (reason === 'T1_PARTIAL_PROFIT_BOOKED') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">🎯 T1 (50% Booked)</span>;
  }
  if (reason === 'TARGET_2_HIT') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">🏆 Target 2 Hit (Runner)</span>;
  }
  if (reason === 'RUNNER_BREAKEVEN_EXIT') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold">🔒 Runner Breakeven Exit</span>;
  }
  if (reason === 'PROFIT_LOCKED_35PCT' || reason === 'RUNNER_PROFIT_LOCKED_T1') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold">🛡️ Profit Lock</span>;
  }
  if (reason === 'RISK_FREE_BREAKEVEN') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">🔒 Breakeven (Zero Risk)</span>;
  }
  if (reason === 'STAGNATION_TIME_DECAY_EXIT') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">⏳ Stagnation Exit</span>;
  }
  if (reason === 'INTRADAY_MARKET_CLOSE_SQUAREOFF') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">🕒 15:15 MIS Square-Off</span>;
  }
  if (reason === 'STOP_LOSS_HIT') {
    return <span className="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold">🛑 Stop Loss Hit</span>;
  }
  return <span className="text-slate-400">{reason}</span>;
};

export default function PaperTradingPage() {
  const { 
    paperPortfolio, 
    refreshPaperPortfolio, 
    showToast,
    setActiveTab 
  } = useMarket();

  const [closingId, setClosingId] = useState(null);
  const [resetting, setResetting] = useState(false);

  const handleClosePos = async (posId, symbol) => {
    try {
      setClosingId(posId);
      const res = await closePaperPosition(posId);
      if (res.success) {
        showToast(`✅ Closed #${symbol} paper position. ${res.message}`, 'success');
        refreshPaperPortfolio();
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setClosingId(null);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset virtual paper trading portfolio to ₹10,000 cash?')) return;
    try {
      setResetting(true);
      await resetPaperPortfolio(10000);
      showToast('🔄 Virtual paper trading portfolio reset to ₹10,000.', 'info');
      refreshPaperPortfolio();
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setResetting(false);
    }
  };

  const p = paperPortfolio || {
    starting_cash: 10000,
    available_cash: 10000,
    margin_locked: 0,
    total_portfolio_value: 10000,
    total_pnl: 0,
    total_pnl_pct: 0,
    open_positions: [],
    closed_trades: [],
    win_rate: 0,
    profit_factor: 1.0,
    wins_count: 0,
    losses_count: 0
  };

  const isProfit = (p.total_pnl || 0) >= 0;

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
      {/* 5-Min AI Auto-Trader Control & Accuracy Panel */}
      <AiAutoTraderPanel 
        onTradeExecuted={refreshPaperPortfolio}
        onSwitchToHistory={() => setActiveTab('history')}
      />
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-emerald-950/30 to-slate-900 rounded-2xl p-5 md:p-6 border border-emerald-500/30 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-mono font-semibold flex items-center gap-1.5">
                <Wallet className="w-3.5 h-3.5 text-emerald-400" />
                VIRTUAL PAPER TRADING SIMULATOR
              </span>
              <span className="px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 text-[11px] font-mono font-bold">
                100% RISK-FREE EXECUTION
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              Live Paper Portfolio <span className="text-emerald-400">& Active Positions</span>
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-1 max-w-2xl">
              Execute Intraday (MIS) and Delivery (CNC) stock recommendations with virtual capital. Tracks real-time P&L against live ticks with automated Target and Stop Loss execution.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={refreshPaperPortfolio}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Refresh P&L</span>
            </button>
            <button
              onClick={handleReset}
              disabled={resetting}
              className="px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-semibold border border-rose-500/30 flex items-center gap-1.5 transition-all"
            >
              <span>{resetting ? 'Resetting...' : 'Reset to ₹10,000'}</span>
            </button>
          </div>
        </div>

        {/* Portfolio Stats Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-4 border-t border-slate-800/80 font-mono">
          <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Total Portfolio Value</div>
            <div className="text-lg font-bold text-white mt-0.5">₹{p.total_portfolio_value?.toLocaleString('en-IN')}</div>
            <div className={`text-xs mt-0.5 font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{p.total_pnl?.toLocaleString('en-IN')} ({p.total_pnl_pct}%)
            </div>
          </div>

          <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Available Cash</div>
            <div className="text-lg font-bold text-emerald-400 mt-0.5">₹{p.available_cash?.toLocaleString('en-IN')}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">Locked: ₹{p.margin_locked?.toLocaleString('en-IN')}</div>
          </div>

          <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Paper Win Rate</div>
            <div className="text-lg font-bold text-cyan-400 mt-0.5">{p.win_rate}%</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{p.wins_count}W - {p.losses_count}L</div>
          </div>

          <div className="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Profit Factor</div>
            <div className="text-lg font-bold text-amber-400 mt-0.5">{p.profit_factor}x</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{p.closed_count || 0} Closed Trades</div>
          </div>
        </div>
      </div>

      {/* AI Coach & Edge Analytics Panel */}
      <AiCoachPanel />

      {/* ACTIVE POSITIONS SECTION */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            Open Paper Positions ({p.open_positions?.length || 0})
          </h2>
          {p.open_positions?.length === 0 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab('recommendations')}
                className="text-xs text-cyan-400 hover:underline flex items-center gap-1 font-mono"
              >
                Go to Intraday Picks →
              </button>
              <span className="text-slate-600">|</span>
              <button
                onClick={() => setActiveTab('delivery')}
                className="text-xs text-indigo-400 hover:underline flex items-center gap-1 font-mono"
              >
                Go to Delivery Picks →
              </button>
            </div>
          )}
        </div>

        {p.open_positions?.length === 0 ? (
          <div className="text-center py-12 bg-slate-900/40 rounded-2xl border border-slate-800 space-y-3">
            <Target className="w-8 h-8 text-slate-500 mx-auto" />
            <p className="text-sm font-semibold text-slate-300">No active paper positions</p>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Click the "Paper Trade" button on any Intraday or Delivery recommendation to simulate the trade live with zero financial risk.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {p.open_positions.map((pos) => {
              const posPnL = pos.unrealized_pnl != null
                ? pos.unrealized_pnl
                : (pos.current_price && pos.entry_price ? (pos.direction === 'SHORT' ? (pos.entry_price - pos.current_price) : (pos.current_price - pos.entry_price)) * (pos.shares || 1) : 0);
              
              const posPnLPct = pos.unrealized_pct != null
                ? pos.unrealized_pct
                : (pos.unrealized_pnl_pct != null
                    ? pos.unrealized_pnl_pct
                    : (pos.entry_price > 0 && pos.current_price
                        ? ((pos.current_price - pos.entry_price) / pos.entry_price * 100 * (pos.direction === 'SHORT' ? -1 : 1))
                        : 0));
              const isWin = posPnL >= 0;
              const isClosing = closingId === pos.position_id;

              return (
                <div
                  key={pos.position_id}
                  className="bg-slate-900/90 rounded-2xl border border-slate-800 hover:border-emerald-500/40 p-4 transition-all shadow-lg space-y-3 font-mono"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-base font-bold text-white">{pos.symbol}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                        pos.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                      }`}>
                        {pos.direction}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {pos.trade_type}
                      </span>
                      {pos.trailing_status === 'PROFIT_LOCKED_35PCT' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-bold animate-pulse">
                          🛡️ 35% PROFIT LOCKED
                        </span>
                      )}
                      {pos.trailing_status === 'RISK_FREE_BREAKEVEN' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                          🔒 ZERO-RISK BREAKEVEN
                        </span>
                      )}
                      {pos.trailing_status === 'T1_BOOKED_RUNNER_ACTIVE' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold animate-pulse">
                          🏃 50% RUNNER (SL @ BREAKEVEN)
                        </span>
                      )}
                      {pos.trailing_status === 'RUNNER_PROFIT_LOCKED_T1' && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                          🏆 RUNNER LOCKED (SL @ T1)
                        </span>
                      )}
                    </div>

                    <div className={`text-sm font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isWin ? '+' : ''}₹{posPnL.toFixed(2)} ({isWin ? '+' : ''}{posPnLPct.toFixed(2)}%)
                    </div>
                  </div>

                  {/* Price Bar */}
                  <div className="grid grid-cols-3 gap-2 bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-center text-xs">
                    <div>
                      <div className="text-[10px] text-slate-500">Entry</div>
                      <div className="text-white font-bold mt-0.5">₹{pos.entry_price?.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500">Current LTP</div>
                      <div className="text-cyan-300 font-bold mt-0.5">₹{pos.current_price?.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-500">Quantity</div>
                      <div className="text-white font-bold mt-0.5">{pos.shares} Shares</div>
                    </div>
                  </div>

                  {/* Target & SL */}
                  <div className="flex items-center justify-between text-xs pt-1">
                    <span className="text-emerald-400 font-semibold">Target 1: ₹{pos.target_1?.toFixed(2)}</span>
                    <span className="text-rose-400 font-semibold flex items-center gap-1.5">
                      <span>Stop Loss: ₹{pos.stop_loss?.toFixed(2)}</span>
                      {pos.trailing_status && (
                        <span className="text-[10px] text-cyan-300 font-semibold">
                          ({pos.trailing_status === 'PROFIT_LOCKED_35PCT' ? 'Locked' : 'Breakeven'})
                        </span>
                      )}
                    </span>
                  </div>

                  {/* Action */}
                  <button
                    onClick={() => handleClosePos(pos.position_id, pos.symbol)}
                    disabled={isClosing}
                    className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl border border-slate-700 transition-colors"
                  >
                    {isClosing ? 'Closing...' : 'Close Position (Market Exit)'}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CLOSED TRADES AUDIT LOG */}
      <div className="space-y-3 pt-4 border-t border-slate-800/80">
        <h2 className="text-base font-bold text-white">Closed Trades History ({p.closed_trades?.length || 0})</h2>
        {p.closed_trades?.length === 0 ? (
          <p className="text-xs text-slate-500 font-mono">No closed trades yet.</p>
        ) : (
          <div className="bg-slate-900/90 rounded-2xl border border-slate-800 overflow-x-auto shadow-md">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase text-[10px]">
                <tr>
                  <th className="p-3">Symbol</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Entry</th>
                  <th className="p-3">Exit</th>
                  <th className="p-3">Qty</th>
                  <th className="p-3">Reason</th>
                  <th className="p-3 text-right">Net P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {p.closed_trades.map((t, idx) => {
                  const pnl = t.realized_pnl || 0;
                  const isWin = pnl >= 0;
                  return (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="p-3 font-bold text-white">{t.symbol}</td>
                      <td className="p-3">{t.trade_type}</td>
                      <td className="p-3">₹{t.entry_price?.toFixed(2)}</td>
                      <td className="p-3">₹{t.exit_price?.toFixed(2)}</td>
                      <td className="p-3">{t.shares}</td>
                      <td className="p-3">{renderExitReasonBadge(t.exit_reason)}</td>
                      <td className={`p-3 text-right font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isWin ? '+' : ''}₹{pnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
