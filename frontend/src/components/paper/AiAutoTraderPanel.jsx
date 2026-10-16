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
  Award,
  PackageCheck,
  PlusCircle,
  Zap,
  SlidersHorizontal,
  ChevronDown
} from 'lucide-react';
import { 
  fetchAiTraderStatus, 
  toggleAiTrader, 
  triggerAiTraderScan, 
  fetchAiTradesAccuracy, 
  retrainFromAiTrades,
  addDeliveryAutoTrade,
  triggerDailyPostMarketRetrain
} from '../../services/api';
import { useMarket } from '../../context/MarketContext';
import { audioAlerts } from '../../utils/audioAlerts';

export default function AiAutoTraderPanel({ onTradeExecuted, onSwitchToHistory }) {
  const { showToast } = useMarket() || {};
  const [status, setStatus] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [toggling, setToggling] = useState(false);

  // Delivery quick-add form state
  const [showAddModal, setShowAddModal] = useState(false);
  const [addSymbol, setAddSymbol] = useState('');
  const [addBudget, setAddBudget] = useState('2000');
  const [addingDelivery, setAddingDelivery] = useState(false);

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
        if (showToast) showToast(`🤖 AI Auto-Trader is now ${res.enabled ? 'ACTIVE' : 'PAUSED'}`);
      }
    } catch (err) {
      console.error(err);
      if (showToast) showToast(`Toggle error: ${err.message}`, 'error');
    } finally {
      setToggling(false);
    }
  };

  const handleToggleIntraday = async () => {
    if (!status) return;
    try {
      setToggling(true);
      const nextVal = !status.enable_intraday;
      const res = await toggleAiTrader({ enabled: status.enabled, enable_intraday: nextVal });
      if (res.success) {
        setStatus(prev => ({ ...prev, enable_intraday: nextVal }));
        if (showToast) showToast(`Intraday Auto-Trading: ${nextVal ? 'ENABLED' : 'DISABLED'}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setToggling(false);
    }
  };

  const handleToggleDelivery = async () => {
    if (!status) return;
    try {
      setToggling(true);
      const nextVal = !status.enable_delivery;
      const res = await toggleAiTrader({ enabled: status.enabled, enable_delivery: nextVal });
      if (res.success) {
        setStatus(prev => ({ ...prev, enable_delivery: nextVal }));
        if (showToast) showToast(`Delivery Auto-Trading: ${nextVal ? 'ENABLED' : 'DISABLED'}`);
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
        const msg = res.scan_result?.message || 'Scan completed successfully.';
        if (showToast) showToast(`🤖 ${msg}`, 'info');
      }
    } catch (err) {
      console.error(err);
      if (showToast) showToast(`Scan error: ${err.message}`, 'error');
    } finally {
      setScanning(false);
    }
  };

  const handleAddDeliveryStock = async (e) => {
    e.preventDefault();
    if (!addSymbol.trim()) return;
    try {
      setAddingDelivery(true);
      const res = await addDeliveryAutoTrade({
        symbol: addSymbol.trim().toUpperCase(),
        budget: parseFloat(addBudget) || 2000
      });
      if (res.success) {
        audioAlerts.playChime('SUCCESS');
        audioAlerts.speak(`Delivery trade added for ${addSymbol.toUpperCase()}`);
        if (showToast) showToast(`✅ Auto-Added #${addSymbol.toUpperCase()} to AI Auto-Trader!`, 'success');
        setAddSymbol('');
        setShowAddModal(false);
        await loadData();
        if (onTradeExecuted) onTradeExecuted();
      }
    } catch (err) {
      audioAlerts.playChime('DANGER');
      if (showToast) showToast(`Error: ${err.message}`, 'error');
    } finally {
      setAddingDelivery(false);
    }
  };

  const handleRetrain = async () => {
    try {
      setRetraining(true);
      const res = await triggerDailyPostMarketRetrain(true);
      if (res.started || res.success) {
        if (showToast) {
          showToast(`🚀 ${res.message || 'Post-market daily model retraining started!'}`, 'success');
        } else {
          alert(`🚀 ${res.message || 'Post-market daily model retraining started!'}`);
        }
      } else {
        if (showToast) {
          showToast(`⚠️ ${res.message}`, 'warning');
        } else {
          alert(`⚠️ ${res.message}`);
        }
      }
      await loadData();
    } catch (err) {
      if (showToast) {
        showToast(`❌ Retraining error: ${err.message}`, 'error');
      } else {
        alert(`❌ Retraining error: ${err.message}`);
      }
    } finally {
      setRetraining(false);
    }
  };

  const isRetrainingActive = retraining || Boolean(status?.is_training);
  const isEnabled = status?.enabled ?? true;
  const isIntradayActive = status?.enable_intraday ?? true;
  const isDeliveryActive = status?.enable_delivery ?? true;

  const winRate = accuracy?.win_rate ?? 0;
  const profitFactor = accuracy?.profit_factor ?? 1.0;
  const isGood = winRate >= 50;

  return (
    <div className="bg-gradient-to-r from-slate-900 via-purple-950/20 to-slate-900 rounded-2xl border border-purple-500/30 p-5 shadow-xl space-y-4">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/40 text-[11px] font-mono font-bold flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5 text-purple-400" />
              AI 5-MIN DUAL AUTO-TRADER
            </span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold flex items-center gap-1 ${
              isEnabled 
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 animate-pulse'
                : 'bg-slate-800 text-slate-400 border border-slate-700'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isEnabled ? 'bg-emerald-400' : 'bg-slate-500'}`} />
              {isEnabled ? 'ACTIVE (EVERY 5 MIN)' : 'PAUSED'}
            </span>

            {/* Daily Auto-Retrain Badge */}
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1" title="Automated post-market model retraining schedule">
              <Clock className="w-3 h-3 text-amber-400" />
              <span>POST-MARKET RETRAIN: 15:45 IST ({status?.daily_training?.next_scheduled_run ? status.daily_training.next_scheduled_run : 'Daily Mon-Fri'})</span>
            </span>

            {/* Mode Switches */}
            <button
              onClick={handleToggleIntraday}
              disabled={toggling}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition-colors flex items-center gap-1 ${
                isIntradayActive
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 hover:bg-cyan-500/30'
                  : 'bg-slate-800/80 text-slate-500 border-slate-700 hover:text-slate-400'
              }`}
              title="Click to toggle Intraday (MIS) auto-trading"
            >
              <Zap className="w-3 h-3 text-cyan-400" />
              <span>MIS INTRADAY: {isIntradayActive ? 'ON' : 'OFF'}</span>
            </button>

            <button
              onClick={handleToggleDelivery}
              disabled={toggling}
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold border transition-colors flex items-center gap-1 ${
                isDeliveryActive
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40 hover:bg-indigo-500/30'
                  : 'bg-slate-800/80 text-slate-500 border-slate-700 hover:text-slate-400'
              }`}
              title="Click to toggle Delivery (CNC) auto-trading"
            >
              <PackageCheck className="w-3 h-3 text-indigo-400" />
              <span>CNC DELIVERY: {isDeliveryActive ? 'ON' : 'OFF'}</span>
            </button>
          </div>

          <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            Automated Intraday &amp; Delivery Trading Engine
            <span className="text-xs font-normal text-emerald-400 font-mono">
              (Auto SL · 50% Breakeven Trailing · Target 1 Exit)
            </span>
          </h3>

          <p className="text-xs text-slate-400">
            Automatically evaluates and enters high-conviction Intraday (MIS) &amp; Delivery (CNC) setups. Positions are managed with active 3-second live price tracking, automatic trailing stop to breakeven at 50% target, and automated profit booking at Target 1.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShowAddModal(prev => !prev)}
            className="px-3 py-2 rounded-xl bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 text-xs font-semibold border border-indigo-500/40 flex items-center gap-1.5 transition-all shadow-md"
            title="Auto-add any delivery stock to AI management"
          >
            <PlusCircle className="w-3.5 h-3.5 text-indigo-300" />
            <span>Auto-Add Delivery</span>
          </button>

          <button
            onClick={handleScanNow}
            disabled={scanning}
            className="px-3 py-2 rounded-xl bg-purple-600/30 hover:bg-purple-600/50 text-purple-200 text-xs font-semibold border border-purple-500/40 flex items-center gap-1.5 transition-all shadow-md"
            title="Force immediate 5-minute scan cycle for both Intraday and Delivery"
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
            disabled={isRetrainingActive}
            className={`px-3 py-2 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-all ${
              isRetrainingActive
                ? 'bg-cyan-950/40 text-cyan-400/60 border-cyan-800/40 cursor-not-allowed'
                : 'bg-slate-800 hover:bg-slate-700 text-cyan-300 border-slate-700 hover:border-cyan-500/50 shadow-sm'
            }`}
            title="Immediately trigger full post-market dual-model retraining (Intraday + Delivery) with latest candles and trade feedback"
          >
            <BrainCircuit className={`w-3.5 h-3.5 ${isRetrainingActive ? 'animate-spin text-cyan-400' : 'text-cyan-400'}`} />
            <span>{isRetrainingActive ? (status?.daily_training?.current_phase || 'Retraining...') : 'Daily Retrain (AI)'}</span>
          </button>
        </div>
      </div>

      {/* Auto-Add Delivery Stock Popup Form */}
      {showAddModal && (
        <form 
          onSubmit={handleAddDeliveryStock}
          className="bg-slate-950/90 border border-indigo-500/40 rounded-xl p-3.5 space-y-3 animate-fade-in"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <PackageCheck className="w-4 h-4 text-indigo-400" />
              Auto-Add Delivery Share to AI Trader
            </span>
            <span className="text-[11px] text-slate-400">
              AI calculates entry, Target 1, Target 2 &amp; Stop-loss automatically
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <label className="text-[10px] text-slate-400 uppercase font-semibold font-mono block mb-1">Stock Symbol</label>
              <input
                type="text"
                placeholder="e.g. TATASTEEL, BEL, RELIANCE"
                value={addSymbol}
                onChange={(e) => setAddSymbol(e.target.value.toUpperCase())}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white uppercase font-mono focus:border-indigo-500 focus:outline-none"
                required
              />
            </div>

            <div>
              <label className="text-[10px] text-slate-400 uppercase font-semibold font-mono block mb-1">Capital Budget (₹)</label>
              <input
                type="number"
                placeholder="2000"
                value={addBudget}
                onChange={(e) => setAddBudget(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="flex items-end gap-2">
              <button
                type="submit"
                disabled={addingDelivery}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs py-1.5 px-3 rounded-lg flex items-center justify-center gap-1.5 transition-all shadow-md"
              >
                {addingDelivery ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                <span>{addingDelivery ? 'Adding...' : 'Trade Delivery Automatically'}</span>
              </button>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs py-1.5 px-2.5 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

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
          <div className="text-[10px] text-slate-400 uppercase font-semibold">Mode Breakdown</div>
          <div className="text-xs font-bold text-slate-200 mt-1 flex items-center justify-between">
            <span className="text-cyan-400">{accuracy?.intraday_closed_count || 0} Intraday</span>
            <span className="text-indigo-400">{accuracy?.delivery_closed_count || 0} Delivery</span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            MIS (5x) &amp; CNC (1x)
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
            Real-time 3s continuous SL &amp; Trailing monitor · Intraday &amp; Delivery Active
          </div>
        </div>
      )}

      {/* Post-Market Model Automation Strip */}
      {status?.daily_training && (
        <div className="bg-slate-950/40 rounded-lg px-3 py-2 border border-slate-800/60 flex flex-wrap items-center justify-between text-[11px] font-mono text-slate-400 gap-2">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-3.5 h-3.5 text-cyan-400" />
            <span>Post-Market Auto-Train: <strong className="text-slate-300">15:45 IST Daily</strong> (Next: <strong className="text-amber-400">{status.daily_training.next_scheduled_run}</strong>)</span>
          </div>
          <div className="text-slate-500">
            {status.daily_training.last_trained_date ? `Last Completed: ${status.daily_training.last_trained_date} (0 downtime hot-swap)` : 'Dual models active & calibrated'}
          </div>
        </div>
      )}
    </div>
  );
}
