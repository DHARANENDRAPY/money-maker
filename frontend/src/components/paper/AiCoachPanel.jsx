import React, { useState, useEffect } from 'react';
import { 
  Sparkles, TrendingUp, TrendingDown, Clock, ShieldCheck, 
  BarChart2, RefreshCw, AlertTriangle, ChevronDown, ChevronUp, Award
} from 'lucide-react';
import { fetchAiCoachAnalytics } from '../../services/api';

export default function AiCoachPanel() {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);

  const loadCoachData = async () => {
    try {
      setLoading(true);
      const data = await fetchAiCoachAnalytics();
      setAnalytics(data);
    } catch (err) {
      console.error('Failed to load AI Coach data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCoachData();
  }, []);

  if (!analytics && loading) {
    return (
      <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-4 text-center text-xs text-slate-500 font-mono">
        <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-cyan-400" />
        Analyzing trading edge & sector distributions...
      </div>
    );
  }

  if (!analytics?.has_data) {
    return (
      <div className="bg-slate-900/50 rounded-2xl border border-slate-800/80 p-4 font-mono text-xs text-slate-400 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span>{analytics?.message || 'Execute trades to unlock AI Coach edge diagnostics.'}</span>
        </div>
        <button
          onClick={loadCoachData}
          className="p-1 hover:text-white transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 rounded-2xl border border-indigo-500/30 p-5 shadow-xl space-y-4 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>AI Trade Coach &amp; Edge Analytics</span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                PRO EDGE
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 font-sans">
              Algorithmic post-mortem of {analytics.total_trades} executed trades across sectors &amp; sessions.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadCoachData}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors"
            title="Refresh Coach Analytics"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors"
          >
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <>
          {/* Key Metric Strips */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-xs">
            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Total Net P&amp;L</div>
              <div className={`text-base font-bold mt-0.5 ${analytics.total_net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {analytics.total_net_pnl >= 0 ? '+' : ''}₹{analytics.total_net_pnl.toLocaleString('en-IN')}
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Edge Win Rate</div>
              <div className="text-base font-bold text-cyan-400 mt-0.5">
                {analytics.overall_win_rate}%
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Profit Factor</div>
              <div className="text-base font-bold text-amber-400 mt-0.5">
                {analytics.profit_factor}x
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase font-semibold">Avg Win / Avg Loss</div>
              <div className="text-xs font-bold text-slate-200 mt-1">
                <span className="text-emerald-400">₹{analytics.avg_win}</span> / <span className="text-rose-400">₹{analytics.avg_loss}</span>
              </div>
            </div>
          </div>

          {/* AI Coach Actionable Insights Box */}
          <div className="bg-indigo-950/30 rounded-xl border border-indigo-500/20 p-3.5 space-y-2">
            <div className="text-[11px] font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5 text-indigo-400" />
              <span>Coach Insights &amp; Execution Directives</span>
            </div>
            <div className="space-y-1.5 text-xs text-slate-300 font-sans">
              {analytics.coach_insights?.map((insight, idx) => (
                <div key={idx} className="flex items-start gap-2 bg-slate-950/40 p-2 rounded-lg border border-indigo-500/10">
                  <span className="text-indigo-400 mt-0.5">•</span>
                  <span>{insight}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Dual Column: Sector Edge & Session Timing */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
            {/* Sector Edge Breakdown */}
            <div className="bg-slate-950/70 rounded-xl border border-slate-800/80 p-3.5 space-y-2.5">
              <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center justify-between">
                <span>Sector Alpha Matrix</span>
                <span className="text-[10px] text-slate-500">Win Rate %</span>
              </div>
              <div className="space-y-2 text-xs">
                {analytics.sector_breakdown?.map((sec, idx) => {
                  const isProfit = sec.net_pnl >= 0;
                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-slate-300 font-semibold">{sec.sector} ({sec.trades} trades)</span>
                        <div className="flex items-center gap-2">
                          <span className={`font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {isProfit ? '+' : ''}₹{sec.net_pnl.toFixed(2)}
                          </span>
                          <span className="text-cyan-400 font-bold w-10 text-right">{sec.win_rate}%</span>
                        </div>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all ${sec.win_rate >= 60 ? 'bg-emerald-500' : (sec.win_rate >= 40 ? 'bg-amber-500' : 'bg-rose-500')}`}
                          style={{ width: `${Math.min(100, Math.max(5, sec.win_rate))}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Session Time of Day Breakdown */}
            <div className="bg-slate-950/70 rounded-xl border border-slate-800/80 p-3.5 space-y-2.5">
              <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center justify-between">
                <span>Session Timing Edge</span>
                <span className="text-[10px] text-slate-500">IST Sessions</span>
              </div>
              <div className="space-y-2.5 text-xs">
                {analytics.time_of_day_breakdown?.map((slot, idx) => {
                  const isProfit = slot.net_pnl >= 0;
                  return (
                    <div key={idx} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between">
                      <div>
                        <div className="text-[11px] text-white font-semibold flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-cyan-400" />
                          <span>{slot.slot}</span>
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {slot.trades} total trades ({slot.wins} wins)
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-bold text-cyan-400">
                          {slot.win_rate}% WR
                        </div>
                        <div className={`text-[11px] font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isProfit ? '+' : ''}₹{slot.net_pnl.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
