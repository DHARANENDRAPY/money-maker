import React, { useState, useEffect, useCallback } from 'react';
import {
  Flame, TrendingUp, TrendingDown, Target, ShieldAlert,
  RefreshCw, Send, CheckCircle2, Clock, DollarSign,
  Layers, Info, Check, Zap, Percent, Activity, BarChart2
} from 'lucide-react';
import { 
  fetchOptionsRadar, 
  broadcastOptionsToTelegram, 
  placePaperTrade,
  fetchTelegramStatus 
} from '../../services/api';
import { useMarket } from '../../context/MarketContext';
import { audioAlerts } from '../../utils/audioAlerts';

const OPTIONS_BUDGET_PRESETS = [
  { value: 600, label: '₹600 (Hero-Zero)', badge: '⚡ Ultra-Low' },
  { value: 1000, label: '₹1,000 (1 Lot)', badge: '🔥 Popular' },
  { value: 2500, label: '₹2,500 (2 Lots)' },
  { value: 5000, label: '₹5,000 (Multi-Lot)' }
];

export default function OptionsRadarPage() {
  const { showToast, refreshPaperPortfolio, setIsPaperDrawerOpen } = useMarket();
  const [budget, setBudget] = useState(1000);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [broadcasting, setBroadcasting] = useState(false);
  const [paperTradingId, setPaperTradingId] = useState(null);
  const [sentSingle, setSentSingle] = useState({});

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetchOptionsRadar(budget);
      setData(res);
    } catch (err) {
      showToast(err.message || 'Failed to load options radar');
    } finally {
      setLoading(false);
    }
  }, [budget, showToast]);

  useEffect(() => {
    loadData();
    fetchTelegramStatus().then(setTelegramStatus).catch(() => {});
  }, [loadData]);

  const handleBroadcastTop = async (setupId = null) => {
    if (!telegramStatus?.enabled) {
      showToast('⚠️ Please configure Telegram Bot Token in Settings first');
      return;
    }
    try {
      if (setupId) setSentSingle(prev => ({ ...prev, [setupId]: 'sending' }));
      else setBroadcasting(true);

      const res = await broadcastOptionsToTelegram({ setup_id: setupId, budget });
      if (res.success) {
        if (setupId) setSentSingle(prev => ({ ...prev, [setupId]: 'sent' }));
        showToast('✅ Broadcasted Options Setup to Telegram!', 'success');
      } else {
        showToast('❌ Telegram alert failed.', 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setBroadcasting(false);
    }
  };

  const handlePaperTrade = async (setup) => {
    try {
      setPaperTradingId(setup.id);
      const res = await placePaperTrade({
        symbol: setup.contract,
        direction: 'LONG',
        trade_type: 'INTRADAY',
        entry_price: setup.entry_premium,
        target_1: setup.target_1_premium,
        target_2: setup.target_2_premium,
        stop_loss: setup.stop_loss_premium,
        shares: setup.lot_size,
        budget: setup.cost_per_lot,
        strategy: 'Options Buying Scalp'
      });

      if (res.success) {
        audioAlerts.playChime('SUCCESS');
        showToast(`🎮 Placed Paper Order: 1 Lot ${setup.contract} @ ₹${setup.entry_premium}!`, 'success');
        refreshPaperPortfolio();
        setIsPaperDrawerOpen(true);
      }
    } catch (err) {
      showToast(`Paper trade error: ${err.message}`, 'error');
    } finally {
      setPaperTradingId(null);
    }
  };

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-amber-950/40 to-slate-900 rounded-2xl p-5 md:p-6 border border-amber-500/30 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs font-mono font-semibold flex items-center gap-1.5">
                <Flame className="w-3.5 h-3.5 text-amber-400" />
                NIFTY & BANKNIFTY OPTIONS RADAR
              </span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 text-[11px] font-mono font-bold">
                Small Budget Friendly (₹500 – ₹1.5k)
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              Weekly Options Buying <span className="text-amber-400">High-Gamma Setups</span>
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-1 max-w-2xl">
              Algorithmic PCR analysis and momentum breakout setups designed specifically for 1-lot retail options buyers with defined risk.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={loadData}
              disabled={loading}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-amber-400' : ''}`} />
              <span>Refresh</span>
            </button>
            <button
              onClick={() => handleBroadcastTop(null)}
              disabled={broadcasting}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white text-xs font-semibold shadow-lg shadow-amber-500/25 flex items-center gap-1.5 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{broadcasting ? 'Sending...' : 'Broadcast to Telegram'}</span>
            </button>
          </div>
        </div>

        {/* Spot & PCR Indices Tracker */}
        {data && (
          <div className="mt-5 pt-4 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">NIFTY 50 Spot</div>
              <div className="text-sm font-bold text-white mt-0.5">
                {data.nifty_spot}{' '}
                <span className={`text-xs ${data.nifty_change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ({data.nifty_change_pct >= 0 ? '+' : ''}{data.nifty_change_pct}%)
                </span>
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">NIFTY PCR Ratio</div>
              <div className="text-sm font-bold text-cyan-400 mt-0.5">
                {data.nifty_pcr}{' '}
                <span className="text-[10px] font-sans text-slate-400 font-normal">({data.nifty_sentiment})</span>
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">BANKNIFTY Spot</div>
              <div className="text-sm font-bold text-white mt-0.5">
                {data.banknifty_spot}{' '}
                <span className={`text-xs ${data.banknifty_change_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  ({data.banknifty_change_pct >= 0 ? '+' : ''}{data.banknifty_change_pct}%)
                </span>
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase">BANKNIFTY PCR</div>
              <div className="text-sm font-bold text-purple-400 mt-0.5">
                {data.banknifty_pcr}
              </div>
            </div>
          </div>
        )}

        {/* Budget Selector */}
        <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between flex-wrap gap-2">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Filter by Options Budget:
          </span>
          <div className="flex items-center gap-2">
            {OPTIONS_BUDGET_PRESETS.map((p) => (
              <button
                key={p.value}
                onClick={() => setBudget(p.value)}
                className={`px-3 py-1 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 ${
                  budget === p.value
                    ? 'bg-amber-500 text-slate-950 font-bold shadow-md shadow-amber-500/20'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700'
                }`}
              >
                <span>{p.label}</span>
                {p.badge && budget !== p.value && (
                  <span className="text-[9px] bg-amber-500/20 text-amber-300 px-1 rounded">
                    {p.badge}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Options Setups Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <RefreshCw className="w-8 h-8 text-amber-400 animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Analyzing Option Chains and Gamma acceleration...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.setups?.map((setup) => {
            const isCall = setup.option_type.includes('CALL');
            const isSingleSending = sentSingle[setup.id] === 'sending';
            const isSingleSent = sentSingle[setup.id] === 'sent';
            const isTrading = paperTradingId === setup.id;

            return (
              <div
                key={setup.id}
                className="bg-slate-900/90 rounded-2xl border border-slate-800 hover:border-amber-500/40 transition-all shadow-lg flex flex-col justify-between overflow-hidden"
              >
                <div className="p-4 bg-gradient-to-b from-slate-900 to-slate-950/40 space-y-3">
                  {/* Top Contract Title */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-white text-base">
                          {setup.contract}
                        </span>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                          isCall ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        }`}>
                          {setup.option_type}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {setup.index} · {setup.expiry}
                      </div>
                    </div>

                    <div className="text-right font-mono">
                      <div className="text-sm font-bold text-amber-400">
                        ₹{setup.entry_premium.toFixed(1)}
                      </div>
                      <div className="text-[10px] text-slate-500">Premium</div>
                    </div>
                  </div>

                  {/* Buy Zone & Targets Box */}
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400 font-medium">Buy Premium Zone:</span>
                      <span className="font-mono font-bold text-white">{setup.premium_buy_zone}</span>
                    </div>

                    <div className="grid grid-cols-3 gap-1.5 text-center font-mono text-xs">
                      <div className="bg-rose-500/10 p-1.5 rounded-lg border border-rose-500/20">
                        <div className="text-[9px] text-rose-400">SL Premium</div>
                        <div className="font-bold text-white">₹{setup.stop_loss_premium}</div>
                        <div className="text-[8.5px] text-rose-400">-{setup.stop_loss_risk_pct}%</div>
                      </div>
                      <div className="bg-emerald-500/10 p-1.5 rounded-lg border border-emerald-500/20">
                        <div className="text-[9px] text-emerald-400">Target 1</div>
                        <div className="font-bold text-white">₹{setup.target_1_premium}</div>
                        <div className="text-[8.5px] text-emerald-300">+{setup.target_1_gain_pct}%</div>
                      </div>
                      <div className="bg-cyan-500/10 p-1.5 rounded-lg border border-cyan-500/20">
                        <div className="text-[9px] text-cyan-400">Target 2</div>
                        <div className="font-bold text-white">₹{setup.target_2_premium}</div>
                        <div className="text-[8.5px] text-cyan-300">+{setup.target_2_gain_pct}%</div>
                      </div>
                    </div>
                  </div>

                  {/* 1 Lot Capital & Profit Details */}
                  <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800 text-[11px] font-mono space-y-1">
                    <div className="flex justify-between text-slate-300">
                      <span>Capital for 1 Lot ({setup.lot_size} Qty):</span>
                      <strong className="text-white">₹{setup.cost_per_lot.toLocaleString('en-IN')}</strong>
                    </div>
                    <div className="flex justify-between text-emerald-400">
                      <span>Profit at Target 1:</span>
                      <strong>+₹{setup.profit_target_1.toLocaleString('en-IN')}</strong>
                    </div>
                    <div className="flex justify-between text-rose-400">
                      <span>Max Risk at SL:</span>
                      <strong>-₹{setup.max_risk_at_sl.toLocaleString('en-IN')}</strong>
                    </div>
                  </div>

                  {/* Catalyst */}
                  <div className="text-[10.5px] text-slate-400 leading-tight">
                    <strong className="text-amber-400">⚡ Catalyst:</strong> {setup.technical_catalyst}
                  </div>
                </div>

                {/* Card Actions */}
                <div className="p-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between gap-2">
                  <button
                    onClick={() => handlePaperTrade(setup)}
                    disabled={isTrading}
                    className="flex-1 px-3 py-2 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 font-semibold text-xs border border-emerald-500/40 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50"
                  >
                    <span>{isTrading ? 'Placing...' : '🎮 Paper Trade 1 Lot'}</span>
                  </button>

                  <button
                    onClick={() => handleBroadcastTop(setup.id)}
                    disabled={isSingleSending || isSingleSent}
                    className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700 transition-all flex items-center justify-center"
                    title="Send Alert to Telegram"
                  >
                    {isSingleSent ? <Check className="w-4 h-4 text-emerald-400" /> : <Send className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
