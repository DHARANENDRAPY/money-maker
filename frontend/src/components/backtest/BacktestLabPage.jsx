import React, { useState } from 'react';
import { 
  FlaskConical, Play, RotateCcw, TrendingUp, TrendingDown, 
  ShieldCheck, Target, Award, Calendar, BarChart3, AlertCircle, CheckCircle2 
} from 'lucide-react';
import { runBacktestSimulation } from '../../services/api';
import { useMarket } from '../../context/MarketContext';

const UNIVERSE_SYMBOLS = [
  "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN",
  "TATAMOTORS", "BHARTIARTL", "ITC", "LT", "SUNPHARMA", "AXISBANK",
  "MARUTI", "TITAN", "BAJFINANCE", "KOTAKBANK", "WIPRO", "HCLTECH",
  "ASIANPAINT", "NTPC", "TATASTEEL", "IOC", "ONGC", "BEL",
  "IRFC", "ZOMATO", "BHEL", "GAIL", "NMDC", "COALINDIA",
  "VEDL", "POWERGRID", "TATAPOWER", "FEDERALBNK", "ASHOKLEY"
];

export default function BacktestLabPage() {
  const { showToast } = useMarket();

  const [symbol, setSymbol] = useState("RELIANCE");
  const [days, setDays] = useState(30);
  const [timeframe, setTimeframe] = useState("5m");
  const [capital, setCapital] = useState(100000);
  const [budget, setBudget] = useState(10000);
  const [strategy, setStrategy] = useState("AI_ENSEMBLE");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleRunBacktest = async (e) => {
    if (e) e.preventDefault();
    try {
      setLoading(true);
      const res = await runBacktestSimulation({
        symbol,
        days: Number(days),
        timeframe,
        initial_capital: Number(capital),
        budget_per_trade: Number(budget),
        strategy
      });
      setResult(res);
      showToast(`✅ Simulation completed for #${symbol}: ${res.win_rate}% Win Rate (${res.total_trades} trades)`, 'success');
    } catch (err) {
      console.error(err);
      showToast(`Backtest Error: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const renderExitBadge = (reason) => {
    if (reason === 'T1_PARTIAL_PROFIT_BOOKED') {
      return <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">🎯 T1 (50% Booked)</span>;
    }
    if (reason === 'TARGET_2_HIT') {
      return <span className="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">🏆 Target 2 (Runner)</span>;
    }
    if (reason === 'RUNNER_BREAKEVEN_EXIT') {
      return <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold">🔒 Runner Breakeven</span>;
    }
    if (reason === 'PROFIT_LOCKED_35PCT' || reason === 'RUNNER_PROFIT_LOCKED_T1') {
      return <span className="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold">🛡️ Profit Lock</span>;
    }
    if (reason === 'STOP_LOSS_HIT') {
      return <span className="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold">🛑 Stop Loss Hit</span>;
    }
    return <span className="text-slate-400 text-[10px]">{reason}</span>;
  };

  return (
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto font-mono">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              <FlaskConical className="w-5 h-5" />
            </span>
            <span>AI Strategy Backtester &amp; Simulation Lab</span>
          </h1>
          <p className="text-xs text-slate-400 font-sans mt-1">
            Simulate the multi-target ensemble strategy, 2-tier trailing stops, and volume filters over historical candle data.
          </p>
        </div>
      </div>

      {/* Configuration Card */}
      <form onSubmit={handleRunBacktest} className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-xl space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
          {/* Symbol */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Stock Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-2 text-white font-mono focus:border-cyan-500 focus:outline-none"
            >
              {UNIVERSE_SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Lookback Days */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Lookback Period</label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-2 text-white font-mono focus:border-cyan-500 focus:outline-none"
            >
              <option value={15}>15 Days</option>
              <option value={30}>30 Days (Recommended)</option>
              <option value={60}>60 Days</option>
              <option value={90}>90 Days</option>
            </select>
          </div>

          {/* Timeframe */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Candle Frame</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-2 text-white font-mono focus:border-cyan-500 focus:outline-none"
            >
              <option value="5m">5-Minute (Intraday MIS)</option>
              <option value="1d">Daily (Swing Delivery)</option>
            </select>
          </div>

          {/* Capital */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Starting Capital (₹)</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-2 text-white font-mono focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Budget per trade */}
          <div>
            <label className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Trade Budget (₹)</label>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-2 text-white font-mono focus:border-cyan-500 focus:outline-none"
            />
          </div>

          {/* Run Button */}
          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 disabled:opacity-50 text-white font-bold py-2 px-4 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-cyan-600/20 transition-all text-xs"
            >
              {loading ? <RotateCcw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{loading ? 'Running...' : 'Run Simulation'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Results View */}
      {result && (
        <div className="space-y-6">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-md">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Simulated Win Rate</div>
              <div className="text-2xl font-bold text-cyan-400 mt-1">{result.win_rate}%</div>
              <div className="text-[11px] text-slate-500 mt-1">
                {result.winning_trades_count}W - {result.losing_trades_count}L ({result.total_trades} trades)
              </div>
            </div>

            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-md">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Net Simulated P&amp;L</div>
              <div className={`text-2xl font-bold mt-1 ${result.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {result.net_pnl >= 0 ? '+' : ''}₹{result.net_pnl.toLocaleString('en-IN')}
              </div>
              <div className={`text-[11px] font-bold mt-1 ${result.net_roi_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {result.net_roi_pct >= 0 ? '+' : ''}{result.net_roi_pct}% Return on Capital
              </div>
            </div>

            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-md">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Profit Factor</div>
              <div className="text-2xl font-bold text-amber-400 mt-1">{result.profit_factor}x</div>
              <div className="text-[11px] text-slate-500 mt-1">Gross Profit / Gross Loss</div>
            </div>

            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-4 shadow-md">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Max Drawdown</div>
              <div className="text-2xl font-bold text-rose-400 mt-1">{result.max_drawdown_pct}%</div>
              <div className="text-[11px] text-slate-500 mt-1">Peak-to-Trough: ₹{result.max_drawdown_inr.toLocaleString('en-IN')}</div>
            </div>
          </div>

          {/* Equity Curve SVG Chart */}
          {result.equity_curve && result.equity_curve.length > 1 && (
            <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-xl space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-cyan-400" />
                  <span>Simulated Equity Curve (₹{result.initial_capital.toLocaleString('en-IN')} → ₹{result.final_capital.toLocaleString('en-IN')})</span>
                </h3>
                <span className="text-xs text-slate-400 font-sans">{result.bars_analyzed} candle bars analyzed</span>
              </div>

              {/* Render SVG Line */}
              <div className="h-44 w-full bg-slate-950/80 rounded-xl p-3 border border-slate-800/80 flex items-center justify-center">
                {(() => {
                  const pts = result.equity_curve;
                  const minEq = Math.min(...pts.map(p => p.equity)) * 0.99;
                  const maxEq = Math.max(...pts.map(p => p.equity)) * 1.01;
                  const range = maxEq - minEq || 1;
                  const w = 800;
                  const h = 140;

                  const coords = pts.map((p, idx) => {
                    const x = (idx / (pts.length - 1)) * w;
                    const y = h - ((p.equity - minEq) / range) * (h - 20) - 10;
                    return `${x},${y}`;
                  });

                  const isProfit = result.final_capital >= result.initial_capital;
                  const strokeColor = isProfit ? '#10b981' : '#ef4444';
                  const areaPoints = `0,${h} ${coords.join(' ')} ${w},${h}`;

                  return (
                    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full overflow-visible">
                      <defs>
                        <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.3" />
                          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
                        </linearGradient>
                      </defs>
                      <polygon points={areaPoints} fill="url(#eqGrad)" />
                      <polyline points={coords.join(' ')} fill="none" stroke={strokeColor} strokeWidth="2.5" />
                    </svg>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Simulated Trade Execution Log */}
          <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-xl space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Calendar className="w-4 h-4 text-cyan-400" />
              <span>Simulated Trade History ({result.trade_log?.length || 0} executions)</span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Trade ID</th>
                    <th className="p-3">Side</th>
                    <th className="p-3">Entry Price</th>
                    <th className="p-3">Exit Price</th>
                    <th className="p-3">Shares</th>
                    <th className="p-3">Exit Reason</th>
                    <th className="p-3 text-right">Net P&amp;L</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {result.trade_log?.map((t, idx) => {
                    const isWin = t.net_pnl > 0;
                    return (
                      <tr key={idx} className="hover:bg-slate-800/40">
                        <td className="p-3 font-semibold text-white">{t.trade_id}</td>
                        <td className="p-3 text-emerald-400 font-bold">{t.direction}</td>
                        <td className="p-3">₹{t.entry_price?.toFixed(2)}</td>
                        <td className="p-3">₹{t.exit_price?.toFixed(2)}</td>
                        <td className="p-3">{t.shares}</td>
                        <td className="p-3">{renderExitBadge(t.exit_reason)}</td>
                        <td className={`p-3 text-right font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isWin ? '+' : ''}₹{t.net_pnl.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
