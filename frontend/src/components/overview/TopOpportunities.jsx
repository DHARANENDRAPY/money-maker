import React from 'react';
import { Target, ArrowRight, Zap, CheckCircle, Clock } from 'lucide-react';
import { useMarket } from '../../context/MarketContext';

export default function TopOpportunities({ signals = [] }) {
  const { setSelectedSymbol, setActiveTab } = useMarket();

  const handleInspect = (sym) => {
    setSelectedSymbol(sym);
    setActiveTab('analysis');
  };

  return (
    <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Zap className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Active Setup Opportunities</h3>
        </div>
        <button
          onClick={() => setActiveTab('scanner')}
          className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1"
        >
          <span>View All in Scanner</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      {signals.length === 0 ? (
        <div className="text-center py-10 text-slate-500 text-xs">
          <Target className="w-8 h-8 mx-auto mb-2 text-slate-600" />
          <p>No high-probability setups active right now. Scanner monitoring 20 NSE stocks.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {signals.slice(0, 3).map((sig) => {
            const isLong = sig.direction === 'LONG';
            return (
              <div
                key={sig.signal_id}
                onClick={() => handleInspect(sig.symbol)}
                className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-cyan-500/40 cursor-pointer transition-all hover:shadow-lg hover:shadow-cyan-500/5 group"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-sm text-white group-hover:text-cyan-400 transition-colors font-mono">
                      {sig.symbol}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold font-mono ${
                      isLong ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                    }`}>
                      {sig.direction}
                    </span>
                  </div>

                  <span className="text-[10.5px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800/60 font-semibold">
                    {Math.round((sig.ml_probability || 0.65) * 100)}% Win Prob
                  </span>
                </div>

                <div className="mt-2 text-xs font-medium text-slate-300 flex items-center justify-between">
                  <span>{sig.strategy}</span>
                  <span className="text-[10px] text-cyan-400 font-mono font-semibold">R:R 1:{sig.risk_reward_ratio?.toFixed(1) || '2.0'}</span>
                </div>

                {/* Pricing Levels */}
                <div className="grid grid-cols-3 gap-1.5 mt-3 pt-2.5 border-t border-slate-800/80 text-[11px] font-mono">
                  <div>
                    <span className="text-[10px] text-slate-400 block">Trigger Entry</span>
                    <span className="text-white font-bold">₹{sig.entry_price?.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-rose-400 block">Stop (Exit)</span>
                    <span className="text-rose-300 font-bold">₹{sig.stop_loss?.toFixed(2)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-emerald-400 block">Target (TP)</span>
                    <span className="text-emerald-300 font-bold">₹{sig.target_price?.toFixed(2)}</span>
                  </div>
                </div>

                {/* Entry Action Guideline */}
                <div className="mt-2 text-[10px] text-slate-400 bg-slate-900/60 px-2 py-1 rounded border border-slate-800/70">
                  <span className="text-emerald-400 font-bold">Action: </span>
                  {isLong ? `Enter above ₹${sig.entry_price?.toFixed(1)} on 5m close` : `Enter below ₹${sig.entry_price?.toFixed(1)} on 5m close`}
                </div>

                {/* Supporting factors */}
                {sig.supporting_factors && sig.supporting_factors.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1">
                    {sig.supporting_factors.slice(0, 2).map((fac, i) => (
                      <span key={i} className="text-[9.5px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                        ✓ {fac}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
