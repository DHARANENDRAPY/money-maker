import React, { useState } from 'react';
import {
  X, Wallet, TrendingUp, TrendingDown, Target, ShieldAlert,
  RotateCcw, CheckCircle2, AlertTriangle, ArrowUpRight, ArrowDownRight,
  Clock, DollarSign, Award, Percent, Layers
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { closePaperPosition, resetPaperPortfolio } from '../../services/api';

export default function PaperTradingDrawer() {
  const { 
    isPaperDrawerOpen, 
    setIsPaperDrawerOpen, 
    paperPortfolio, 
    refreshPaperPortfolio, 
    showToast 
  } = useMarket();

  const [closingId, setClosingId] = useState(null);
  const [resetting, setResetting] = useState(false);

  if (!isPaperDrawerOpen) return null;

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
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/70 backdrop-blur-sm flex justify-end animate-fade-in">
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full flex flex-col justify-between shadow-2xl overflow-hidden">
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-sm text-white flex items-center gap-1.5">
                Paper Trading Portfolio <span className="text-[10px] font-mono px-2 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-bold">100% Risk Free</span>
              </h2>
              <p className="text-[11px] text-slate-400">Live P&L Tracking & Automated Exit Execution</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              disabled={resetting}
              title="Reset Portfolio to ₹10,000"
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors border border-slate-700 text-xs flex items-center gap-1"
            >
              <RotateCcw className={`w-3.5 h-3.5 ${resetting ? 'animate-spin' : ''}`} />
              <span className="text-[10.5px]">Reset</span>
            </button>
            <button
              onClick={() => setIsPaperDrawerOpen(false)}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Portfolio Balance & Analytics Grid */}
        <div className="p-4 bg-slate-950/50 border-b border-slate-800 space-y-3">
          <div className="grid grid-cols-3 gap-2.5 text-center font-mono">
            <div className="bg-slate-900/90 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">Portfolio Value</div>
              <div className="text-sm font-bold text-white mt-0.5">
                ₹{p.total_portfolio_value?.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
              </div>
              <div className={`text-[10px] font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                {isProfit ? '+' : ''}₹{p.total_pnl?.toLocaleString('en-IN')} ({isProfit ? '+' : ''}{p.total_pnl_pct}%)
              </div>
            </div>

            <div className="bg-slate-900/90 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">Available Cash</div>
              <div className="text-sm font-bold text-cyan-400 mt-0.5">
                ₹{p.available_cash?.toLocaleString('en-IN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}
              </div>
              <div className="text-[10px] text-slate-500">Margin: ₹{p.margin_locked?.toLocaleString('en-IN')}</div>
            </div>

            <div className="bg-slate-900/90 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">Win Rate</div>
              <div className="text-sm font-bold text-amber-400 mt-0.5">
                {p.win_rate}%
              </div>
              <div className="text-[10px] text-slate-400">PF: <strong>{p.profit_factor}x</strong> ({p.wins_count}W / {p.losses_count}L)</div>
            </div>
          </div>
        </div>

        {/* Positions & Trades Tab Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Active Open Positions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Active Open Positions ({p.open_positions?.length || 0})
              </h3>
            </div>

            {p.open_positions?.length === 0 ? (
              <div className="p-5 rounded-xl bg-slate-950/40 border border-slate-800/80 text-center text-xs text-slate-500 space-y-1">
                <Target className="w-6 h-6 text-slate-600 mx-auto" />
                <p>No active paper trades open right now.</p>
                <p className="text-[11px] text-slate-600">Click <strong>"Paper Trade"</strong> on any Intraday or Delivery card to simulate a trade!</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {p.open_positions.map((pos) => {
                  const isLong = pos.direction === 'LONG';
                  const posProfit = (pos.unrealized_pnl || 0) >= 0;
                  const isClosing = closingId === pos.position_id;

                  return (
                    <div
                      key={pos.position_id}
                      className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition-all space-y-2.5"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-white text-sm">#{pos.symbol}</span>
                            <span className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded ${
                              isLong ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                            }`}>
                              {pos.direction} {pos.trade_type}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">{pos.shares} Qty</span>
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
                            Entry: ₹{pos.entry_price} · Live: ₹{pos.current_price}
                          </div>
                        </div>

                        {/* Floating Live P&L */}
                        <div className="text-right font-mono">
                          <div className={`text-sm font-bold flex items-center justify-end gap-0.5 ${
                            posProfit ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {posProfit ? '+' : ''}₹{pos.unrealized_pnl?.toLocaleString('en-IN')}
                          </div>
                          <div className={`text-[10px] ${posProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                            ({posProfit ? '+' : ''}{pos.unrealized_pct}%)
                          </div>
                        </div>
                      </div>

                      {/* Target & SL Targets */}
                      <div className="grid grid-cols-2 gap-2 text-[10.5px] font-mono bg-slate-900/80 p-2 rounded-lg border border-slate-800/80">
                        <div className="text-emerald-400">
                          🎯 Target 1: ₹{pos.target_1}
                        </div>
                        <div className="text-rose-400 text-right">
                          🛑 Stop Loss: ₹{pos.stop_loss}
                        </div>
                      </div>

                      {/* Exit Action */}
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[10px] text-slate-500 font-mono">
                          Budget: ₹{pos.allocated_budget} (Margin: ₹{pos.margin_used})
                        </span>
                        <button
                          onClick={() => handleClosePos(pos.position_id, pos.symbol)}
                          disabled={isClosing}
                          className="px-2.5 py-1 rounded bg-rose-600/20 hover:bg-rose-600/40 text-rose-300 text-[11px] font-semibold border border-rose-500/30 transition-all disabled:opacity-50"
                        >
                          {isClosing ? 'Closing...' : 'Close Trade'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Closed Trade History Ledger */}
          <div>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              Completed Trade History ({p.closed_trades?.length || 0})
            </h3>

            {p.closed_trades?.length === 0 ? (
              <p className="text-[11px] text-slate-600 italic">No closed trades yet.</p>
            ) : (
              <div className="space-y-2">
                {p.closed_trades.slice(0, 10).map((trade, idx) => {
                  const isWin = (trade.realized_pnl || 0) > 0;
                  return (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/70 flex items-center justify-between text-xs font-mono"
                    >
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-white">#{trade.symbol}</span>
                          <span className="text-[10px] text-slate-500">({trade.direction})</span>
                          <span className="text-[9.5px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">
                            {trade.exit_reason?.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          Entry: ₹{trade.entry_price} → Exit: ₹{trade.exit_price}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className={`font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isWin ? '+' : ''}₹{trade.realized_pnl?.toLocaleString('en-IN')}
                        </div>
                        <div className={`text-[9.5px] ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                          ({isWin ? '+' : ''}{trade.realized_pnl_pct}%)
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-[10.5px] text-slate-400 text-center">
          Positions automatically exit in real-time when Target 1 or Stop Loss is reached on live ticks.
        </div>
      </div>
    </div>
  );
}
