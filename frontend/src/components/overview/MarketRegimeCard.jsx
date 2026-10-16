import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown, Gauge, Shield, PieChart, Layers } from 'lucide-react';
import { fetchPcrSentiment } from '../../services/api';

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

  const [pcrData, setPcrData] = useState(null);

  useEffect(() => {
    let mounted = true;
    fetchPcrSentiment()
      .then(res => {
        if (mounted) setPcrData(res);
      })
      .catch(err => console.warn('PCR Sentiment fetch error:', err));
    return () => { mounted = false; };
  }, []);

  const nPcr = pcrData?.nifty?.pcr ?? 1.08;
  const nPain = pcrData?.nifty?.max_pain ?? 23100;
  const bnPcr = pcrData?.banknifty?.pcr ?? 1.04;
  const bnPain = pcrData?.banknifty?.max_pain ?? 55800;

  return (
    <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <Activity className="w-4 h-4" />
            </div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Market Breadth & PCR Sentiment</h3>
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

        {/* Institutional Put-Call Ratio (PCR) & Max Pain Radar */}
        <div className="mt-3.5 pt-3 border-t border-slate-800/60 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-bold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
              <PieChart className="w-3.5 h-3.5 text-cyan-400" /> Options OI & Max Pain
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${
              nPcr >= 1.05 
                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                : nPcr < 0.85
                ? 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                : 'bg-slate-800 text-slate-300 border-slate-700'
            }`}>
              {nPcr >= 1.05 ? 'Bullish Put Inflow' : nPcr < 0.85 ? 'Call Overhang' : 'Balanced OI'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 font-mono text-center">
            <div className="bg-slate-950/80 p-2 rounded-lg border border-slate-800/60">
              <div className="text-[9.5px] text-slate-400">NIFTY 50 PCR</div>
              <div className="text-xs font-bold text-white mt-0.5">{nPcr} <span className="text-[9.5px] font-normal text-cyan-400">(Pain ₹{nPain})</span></div>
            </div>
            <div className="bg-slate-950/80 p-2 rounded-lg border border-slate-800/60">
              <div className="text-[9.5px] text-slate-400">BANK NIFTY PCR</div>
              <div className="text-xs font-bold text-white mt-0.5">{bnPcr} <span className="text-[9.5px] font-normal text-cyan-400">(Pain ₹{bnPain})</span></div>
            </div>
          </div>

          {pcrData?.nifty?.summary && (
            <div className="text-[10.5px] text-slate-400 font-mono bg-slate-950/40 p-2 rounded-lg border border-slate-800/40 leading-tight">
              💡 {pcrData.nifty.summary}
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 text-[11px] text-slate-400 flex items-center space-x-1.5">
        <Shield className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
        <span>Market regime favors high-conviction setups aligned with institutional flow.</span>
      </div>
    </div>
  );
}

