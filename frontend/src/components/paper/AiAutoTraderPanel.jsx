import React, { useState, useEffect } from 'react';
import {
  Bot,
  Play,
  Pause,
  RefreshCw,
  Sparkles,
  Target,
  ShieldAlert,
  TrendingUp,
  BrainCircuit,
  BarChart3,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  Award
} from 'lucide-react';
import { 
  fetchAiTraderStatus, 
  toggleAiTrader, 
  triggerAiTraderScan, 
  fetchAiTradesAccuracy, 
  retrainFromAiTrades 
} from '../../services/api';

export default function AiAutoTraderPanel({ onTradeExecuted, onSwitchToHistory }) {
  const [status, setStatus] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [toggling, setToggling] = useState(false);

  const loadData = async () => {
    try {
      const [st, acc] = await Promise.all([
        fetchAiTraderStatus(),
        fetchAiTradesAccuracy()
      ]);
      setStatus(st);
      setAccuracy(acc);
    } catch (e) {
      console.warn('Failed to load AI Trader status:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleToggle = async () => {
    if (!status) return;
    try {
      setToggling(true);
      const res = await toggleAiTrader({ enabled: !status.enabled });
      if (res.success) {
        setStatus(prev => ({ ...prev, enabled: res.enabled }));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setToggling(false);
    }
  };

  const handleScanNow = async () => {
    try {
      setScanning(true);
      const res = await triggerAiTraderScan();
      if (res.success) {
        await loadData();
        if (onTradeExecuted) onTradeExecuted();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  const handleRetrain = async () => {
    try {
      setRetraining(true);
      const res = await retrainFromAiTrades();
      alert(res.message);
      await loadData();
    } catch (err) {
      alert(`Retraining error: ${err.message}`);
    } finally {
      setRetraining(false);
    }
  };

  const isEnabled = status?.enabled ?? true;
  const winRate = accuracy?.win_rate ?? 0;
  const profitFactor = accuracy?.profit_factor ?? 1.0;
  const isGood = winRate >= 50;

  return (
    <div className="bg-gradient-to-r from-slate-900 via-purple-950/20 to-slate-900 rounded-2xl border border-purple-500/30 p-5 shadow-xl space-y-4">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[11px] font-mono font-bold flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5 text-purple-400" />
              AI 5-MIN INTRADAY AUTO-TRADER
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold flex items-center gap-1 ${
              isEnabled 
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 animate-pulse'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isEnabled ? 'bg-emerald-400' : 'bg-slate-500'}`} />
              {isEnabled ? 'ACTIVE (EVERY 5 MIN)' : 'PAUSED'}
            </span>
            <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono">
              STRICTLY INTRADAY (NO DELIVERY)
            </span>
          </div>

          <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            Automated High-Win-Rate Execution Engine
            <span className="text-xs font-normal text-emerald-400 font-mono">
              (Gate: AI Confidence &ge; 80% | Auto SL &amp; Breakeven Trailing)
            </span>
          </h3>

          <p className="text-xs text-slate-400">
            Every 5 minutes during market hours, AI scans for high-conviction intraday setups with &ge;80% AI confidence, automatically enters paper trades with stop-loss, moves stop to breakeven at 50% target, and books profit at Target 1.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleScanNow}
            disabled={scanning}
            className="px-3 py-2 rounded-xl bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 text-xs font-semibold border border-purple-500/40 flex items-center gap-1.5 transition-all shadow-md"
            title="Force immediate 5-minute scan cycle"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanning ? 'animate-spin text-purple-300' : ''}`} />
            <span>{scanning ? 'Scanning...' : 'Scan Now (5m)'}</span>
          </button>

          <button
            onClick={handleToggle}
            disabled={toggling}
            className={`px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all border shadow-md ${
              isEnabled 
                ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/40'
                : 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border-emerald-500/40'
            }`}
          >
            {isEnabled ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isEnabled ? 'Pause Bot' : 'Start Auto-Bot'}</span>
          </button>

          <button
            onClick={handleRetrain}
            disabled={retraining}
            className="px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold border border-slate-700 flex items-center gap-1.5 transition-all"
            title="Retrain AI ensemble using closed paper trade outcomes"
          >
            <BrainCircuit className={`w-3.5 h-3.5 ${retraining ? 'animate-spin text-cyan-400' : ''}`} />
            <span>{retraining ? 'Retraining...' : 'Train AI on Trades'}</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-3 border-t border-purple-900/40 font-mono text-xs">
        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-semibold">AI Win Rate</div>
          <div className={`text-base font-bold mt-0.5 ${isGood ? 'text-emerald-400' : 'text-amber-400'}`}>
            {winRate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {accuracy?.closed_trades || 0} completed trades
          </div>
        </div>

        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-semibold">Targets vs Stops</div>
          <div className="text-base font-bold text-white mt-0.5">
            <span className="text-emerald-400">{accuracy?.target_hit_count || 0} TGT</span>
            <span className="text-slate-500 text-xs mx-1">/</span>
            <span className="text-rose-400">{accuracy?.stop_loss_hit_count || 0} SL</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Target hit ratio
          </div>
        </div>

        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-semibold">Net Realized P&L</div>
          <div className={`text-base font-bold mt-0.5 ${(accuracy?.total_net_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {(accuracy?.total_net_pnl || 0) >= 0 ? '+' : ''}₹{(accuracy?.total_net_pnl || 0).toLocaleString('en-IN')}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Profit factor: {profitFactor}x
          </div>
        </div>

        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800">
          <div className="text-[10px] text-slate-400 uppercase font-semibold">Min Threshold</div>
          <div className="text-base font-bold text-purple-300 mt-0.5">
            &gt; 50% ML
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Only &gt;50% win probability
          </div>
        </div>

        <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="text-[10px] text-slate-400 uppercase font-semibold">Dedicated Vault</div>
            <div className="text-base font-bold text-cyan-300 mt-0.5">
              {accuracy?.total_trades || 0} Logged
            </div>
          </div>
          {onSwitchToHistory && (
            <button
              onClick={onSwitchToHistory}
              className="text-[11px] text-cyan-400 hover:text-cyan-300 text-left font-sans flex items-center gap-1 font-semibold underline mt-1"
            >
              View AI Ledger →
            </button>
          )}
        </div>
      </div>

      {/* Last Scan Status Strip */}
      {status?.last_scan_result && (
        <div className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between text-xs font-mono text-slate-400 gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span>Latest Scan: {status.last_scan_result.message || 'Waiting for next 5-min cycle'}</span>
          </div>
          <div className="text-[11px] text-slate-500">
            Next scan in ~5m · strictly Intraday · Delivery ignored
          </div>
        </div>
      )}
    </div>
  );
}
