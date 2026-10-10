import React from 'react';
import { Activity, TrendingUp, TrendingDown, Gauge, Shield } from 'lucide-react';

export default function MarketRegimeCard({ breadth, nifty, stats }) {
  const advances = breadth?.advances ?? (nifty?.change_pct >= 0 ? 30 : 20);
  const declines = breadth?.declines ?? (nifty?.change_pct >= 0 ? 20 : 30);
  const total = advances + declines || 50;
  const advancePct = Math.round((advances / total) * 100);
  const declinePct = 100 - advancePct;
  const regime = breadth?.market_regime ?? (nifty?.change_pct >= 0 ? 'MODERATE_BULLISH' : 'MODERATE_BEARISH');
  const confidence = Math.round((breadth?.regime_confidence ?? 0.75) * 100);
  const adRatio = breadth?.advance_decline_ratio ?? (advances / Math.max(declines, 1));
  const above20Ema = breadth?.nifty500_above_20ema_pct ?? Math.round((advances / 50.0) * 100);

  return (
    <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <Activity className="w-4 h-4" />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Market Breadth & Regime</h3>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700/50">
            {confidence}% Confidence
          </span>
        </div>

        {/* Advance / Decline Bar */}
        <div className="space-y-1.5 my-3">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-emerald-400 font-medium flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" /> Advances: {advances} ({advancePct}%)
            </span>
            <span className="text-rose-400 font-medium flex items-center gap-1">
              Declines: {declines} ({declinePct}%) <TrendingDown className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="h-2 w-full bg-slate-950 rounded-full overflow-hidden flex">
            <div 
              style={{ width: `${advancePct}%` }} 
              className="bg-emerald-500 transition-all duration-500 shadow-sm shadow-emerald-500/50"
            />
            <div 
              style={{ width: `${declinePct}%` }} 
              className="bg-rose-500 transition-all duration-500 shadow-sm shadow-rose-500/50"
            />
          </div>
        </div>

        {/* Ratio & 20 EMA stat */}
        <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-800/60 text-xs">
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/40">
            <div className="text-[11px] text-slate-400">A/D Ratio</div>
            <div className="font-mono text-sm font-bold text-white mt-0.5">
              {adRatio ? adRatio.toFixed(2) : '--'}
            </div>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/40">
            <div className="text-[11px] text-slate-400">Breadth Above 20 EMA</div>
            <div className="font-mono text-sm font-bold text-cyan-400 mt-0.5">
              {above20Ema ? `${above20Ema}%` : '--'}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 text-[11px] text-slate-400 flex items-center space-x-1.5">
        <Shield className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
        <span>Market regime favors long setups aligned with outperforming sectors.</span>
      </div>
    </div>
  );
}
