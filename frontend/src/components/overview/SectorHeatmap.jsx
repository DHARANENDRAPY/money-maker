import React from 'react';
import { Layers, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export default function SectorHeatmap({ sectors = [] }) {
  return (
    <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
            <Layers className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Sector Relative Strength</h3>
        </div>
        <span className="text-[11px] text-slate-400 font-mono">Benchmark: Nifty 50</span>
      </div>

      <div className="space-y-2 mt-2">
        {sectors.slice(0, 6).map((sec) => {
          const isPositive = sec.change_pct >= 0;
          return (
            <div
              key={sec.sector}
              className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40 flex items-center justify-between text-xs hover:border-slate-700 transition-colors"
            >
              <div className="flex flex-col">
                <span className="font-semibold text-slate-200">{sec.sector}</span>
                <span className="text-[10px] text-slate-400 font-mono mt-0.5">
                  Top: <span className="text-slate-300">{sec.top_gainer}</span>
                </span>
              </div>

              <div className="flex items-center space-x-3">
                {/* Relative strength badge */}
                <span className={`text-[10.5px] font-mono px-2 py-0.5 rounded font-medium flex items-center gap-0.5 ${
                  sec.relative_strength >= 0
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                    : 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                }`}>
                  {sec.relative_strength >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  {sec.relative_strength >= 0 ? '+' : ''}{sec.relative_strength.toFixed(2)}% RS
                </span>

                {/* Absolute change */}
                <span className={`font-mono font-bold w-14 text-right ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isPositive ? '+' : ''}{sec.change_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
