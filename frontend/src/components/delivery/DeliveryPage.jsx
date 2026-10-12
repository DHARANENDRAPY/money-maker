import React, { useState, useEffect, useCallback } from 'react';
import {
  PackageCheck, TrendingUp, Sparkles, Target, ArrowUpRight,
  ShieldAlert, RefreshCw, Send, CheckCircle2, Clock, Calendar,
  Wallet, DollarSign, Award, Layers, HelpCircle, ChevronRight,
  Info, Check, Zap, Filter, Star, BarChart3, AlertCircle, Plus, PlusCircle
} from 'lucide-react';
import { 
  fetchDeliveryRecommendations, 
  broadcastDeliveryToTelegram,
  fetchTelegramStatus,
  placePaperTrade
} from '../../services/api';
import { useMarket } from '../../context/MarketContext';
import { audioAlerts } from '../../utils/audioAlerts';

const BUDGET_PRESETS = [
  { value: 1000, label: '₹1,000 (Starter / Micro)', badge: '🔥 User Pick' },
  { value: 5000, label: '₹5,000 (Growth)' },
  { value: 10000, label: '₹10,000 (Standard)' },
  { value: 25000, label: '₹25,000 (Pro)' },
  { value: 50000, label: '₹50,000 (High Capital)' }
];

const HORIZON_TABS = [
  { id: 'ALL', label: 'All Horizons', icon: Layers },
  { id: 'SWING_2_4W', label: '2–4 Weeks (Short Swing)', icon: Clock },
  { id: 'POSITIONAL_1_3M', label: '1–3 Months (Positional)', icon: Calendar },
  { id: 'GROWTH_3_6M', label: '3–6 Months (Growth)', icon: TrendingUp }
];

const PRICE_FILTERS = [
  { id: 0, label: 'All Stock Prices' },
  { id: 100, label: 'Under ₹100 (Penny/Micro)' },
  { id: 500, label: 'Under ₹500 (Affordable)' },
  { id: 1000, label: 'Under ₹1,000 (Mid-Range)' }
];

export default function DeliveryPage() {
  const { liveQuotes, showToast, setIsPaperDrawerOpen, refreshPaperPortfolio } = useMarket();
  const [budget, setBudget] = useState(1000);
  const [customBudgetInput, setCustomBudgetInput] = useState('');
  const [activeHorizon, setActiveHorizon] = useState('ALL');
  const [activePriceFilter, setActivePriceFilter] = useState(0);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [data, setData] = useState(null);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [broadcasting, setBroadcasting] = useState(false);
  const [sentSingle, setSentSingle] = useState({});
  const [paperBuying, setPaperBuying] = useState({});
  const [paperBought, setPaperBought] = useState({});

  const loadData = useCallback(async (isSilent = false) => {
    try {
      if (!isSilent) setIsRefreshing(true);
      const res = await fetchDeliveryRecommendations({
        budget,
        horizon: activeHorizon,
        max_price: activePriceFilter,
        limit: 15
      });
      setData(res);
    } catch (err) {
      console.warn('Delivery fetch error:', err);
    } finally {
      setIsInitialLoading(false);
      setIsRefreshing(false);
    }
  }, [budget, activeHorizon, activePriceFilter]);

  useEffect(() => {
    loadData(false);
    fetchTelegramStatus().then(setTelegramStatus).catch(() => {});
    // Steady background refresh every 30s without clearing the screen
    const interval = setInterval(() => loadData(true), 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleApplyCustomBudget = (e) => {
    e.preventDefault();
    const val = parseFloat(customBudgetInput);
    if (val && val >= 100) {
      setBudget(val);
      setCustomBudgetInput('');
    }
  };

  const handleBroadcastTop = async () => {
    if (!telegramStatus?.enabled) {
      showToast('⚠️ Please configure Telegram Bot Token in Settings first');
      return;
    }
    try {
      setBroadcasting(true);
      const res = await broadcastDeliveryToTelegram({ budget });
      if (res.success) {
        showToast(`✅ ${res.message || 'Broadcasted Delivery Picks to Telegram!'}`);
      } else {
        showToast(`❌ ${res.message || res.error || 'Telegram delivery alert failed.'}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`);
    } finally {
      setBroadcasting(false);
    }
  };

  const handleSendSingle = async (symbol) => {
    if (!telegramStatus?.enabled) {
      showToast('⚠️ Please configure Telegram Bot Token in Settings first');
      return;
    }
    try {
      setSentSingle(prev => ({ ...prev, [symbol]: 'sending' }));
      const res = await broadcastDeliveryToTelegram({ symbol, budget });
      if (res.success) {
        setSentSingle(prev => ({ ...prev, [symbol]: 'sent' }));
        showToast(`✅ Sent #${symbol} Delivery Plan to Telegram!`);
      } else {
        setSentSingle(prev => ({ ...prev, [symbol]: 'idle' }));
        showToast(`❌ Failed: ${res.result?.error || 'Telegram error'}`);
      }
    } catch (err) {
      setSentSingle(prev => ({ ...prev, [symbol]: 'idle' }));
      showToast(`Error: ${err.message}`);
    }
  };

  const handlePaperTrade = async (pick) => {
    const symbol = pick.symbol;
    try {
      setPaperBuying(prev => ({ ...prev, [symbol]: true }));
      const payload = {
        symbol: pick.symbol,
        direction: 'LONG',
        trade_type: 'DELIVERY',
        product_type: 'CNC',
        entry_price: pick.entry_price || pick.ltp,
        quantity: pick.suggested_shares || 1,
        stop_loss: pick.stop_loss,
        target_1: pick.target_1,
        target_2: pick.target_2,
        budget: budget,
        source: 'DELIVERY_PICK'
      };
      const res = await placePaperTrade(payload);
      if (res.success) {
        setPaperBought(prev => ({ ...prev, [symbol]: true }));
        audioAlerts.playChime('SUCCESS');
        audioAlerts.speak(`Paper delivery purchase confirmed for ${pick.suggested_shares} shares of ${pick.symbol}`);
        showToast(`🎮 Paper Buy Confirmed: ${pick.suggested_shares}x ${pick.symbol} (CNC Delivery)`, 'success');
        await refreshPaperPortfolio();
        setIsPaperDrawerOpen(true);
      }
    } catch (err) {
      audioAlerts.playChime('DANGER');
      showToast(`Paper buy error: ${err.message}`, 'error');
    } finally {
      setPaperBuying(prev => ({ ...prev, [symbol]: false }));
    }
  };

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Banner & Header */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 rounded-2xl p-5 md:p-6 border border-indigo-500/30 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-xs font-mono font-semibold flex items-center gap-1.5">
                <PackageCheck className="w-3.5 h-3.5 text-indigo-400" />
                DELIVERY & SWING INTELLIGENCE
              </span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 text-[11px] font-mono font-bold">
                1x CASH (CNC)
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              Buy & Hold Delivery Stocks <span className="text-indigo-400">Execution Plan</span>
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-1 max-w-2xl">
              AI-curated positional stock picks with exact entry buy zones, exit targets, holding time horizons, and position sizing calculated specifically for your budget.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => loadData(false)}
              disabled={isRefreshing}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-indigo-400' : ''}`} />
              <span>Refresh</span>
            </button>

            <button
              onClick={handleBroadcastTop}
              disabled={broadcasting}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 flex items-center gap-1.5 transition-all"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{broadcasting ? 'Sending...' : 'Send Top Picks to Telegram'}</span>
            </button>
          </div>
        </div>

        {/* BUDGET SELECTOR BAR (Tailored for ₹1,000+ Starter Capital) */}
        <div className="mt-5 pt-4 border-t border-slate-800/80">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Select Your Trading Capital:
              </span>
              <span className="text-xs font-mono font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60">
                Active Budget: ₹{budget.toLocaleString('en-IN')}
              </span>
            </div>

            {/* Presets */}
            <div className="flex flex-wrap items-center gap-2">
              {BUDGET_PRESETS.map((p) => {
                const isActive = budget === p.value;
                return (
                  <button
                    key={p.value}
                    onClick={() => setBudget(p.value)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all flex items-center gap-1.5 ${
                      isActive
                        ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                        : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80 border border-slate-700/60'
                    }`}
                  >
                    <span>{p.label}</span>
                    {p.badge && !isActive && (
                      <span className="text-[9.5px] bg-indigo-500/30 text-indigo-300 px-1 py-0.2 rounded font-sans">
                        {p.badge}
                      </span>
                    )}
                  </button>
                );
              })}

              {/* Custom Input */}
              <form onSubmit={handleApplyCustomBudget} className="flex items-center gap-1">
                <input
                  type="number"
                  placeholder="Custom ₹"
                  value={customBudgetInput}
                  onChange={(e) => setCustomBudgetInput(e.target.value)}
                  className="w-24 px-2.5 py-1 text-xs font-mono bg-slate-950 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-indigo-400"
                />
                <button
                  type="submit"
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg border border-slate-700"
                >
                  Set
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>

      {/* FILTER CONTROLS: HORIZON & PRICE */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-900/70 p-3 rounded-xl border border-slate-800/80">
        {/* Horizon Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {HORIZON_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeHorizon === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveHorizon(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Price Bucket Filter */}
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={activePriceFilter}
            onChange={(e) => setActivePriceFilter(Number(e.target.value))}
            className="bg-slate-950 border border-slate-700 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-400 font-medium"
          >
            {PRICE_FILTERS.map((pf) => (
              <option key={pf.id} value={pf.id}>
                {pf.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* DELIVERY PICKS LIST */}
      {isInitialLoading && !data ? (
        <div className="flex flex-col items-center justify-center py-20 space-y-3">
          <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Scanning 40+ NSE stocks for high-probability delivery setups...</p>
        </div>
      ) : data?.recommendations?.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/40 rounded-2xl border border-slate-800 space-y-2">
          <Info className="w-8 h-8 text-slate-500 mx-auto" />
          <p className="text-sm font-semibold text-slate-300">No stocks match your current filter</p>
          <p className="text-xs text-slate-500">Try changing the Time Horizon or Price Filter above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.recommendations.map((pick, idx) => {
            const liveQ = liveQuotes?.[pick.symbol];
            const liveLtp = Number(liveQ?.ltp ?? pick.ltp ?? 0);
            const liveChg = Number(liveQ?.change_pct ?? pick.change_pct ?? 0);
            const isSingleSending = sentSingle[pick.symbol] === 'sending';
            const isSingleSent = sentSingle[pick.symbol] === 'sent';

            return (
              <div
                key={pick.symbol}
                className="bg-slate-900/90 rounded-2xl border border-slate-800 hover:border-indigo-500/40 transition-all shadow-lg overflow-hidden flex flex-col justify-between group"
              >
                {/* Card Header */}
                <div className="p-4 md:p-5 border-b border-slate-800/80 bg-gradient-to-b from-slate-900 to-slate-950/40">
                  <div className="flex items-start justify-between gap-3">
                    {/* Stock Symbol + Name */}
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold font-mono ${
                        idx === 0 ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                        idx === 1 ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' :
                        idx === 2 ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' :
                        'bg-slate-800 text-slate-300 border border-slate-700'
                      }`}>
                        #{pick.rank || idx + 1}
                      </div>

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-white text-base">{pick.symbol}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono font-semibold">
                            {pick.holding_period}
                          </span>
                          {pick.under_500 && (
                            <span className="text-[9.5px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold">
                              ₹1k Friendly
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">{pick.name} · {pick.sector}</div>
                      </div>
                    </div>

                    {/* Price & Rating & Quick + Action */}
                    <div className="flex items-center gap-2.5 shrink-0">
                      <div className="text-right">
                        <div className="text-sm font-mono font-bold text-white">
                          ₹{liveLtp.toFixed(2)}{' '}
                          <span className={`text-xs ${liveChg >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            ({liveChg >= 0 ? '+' : ''}{liveChg.toFixed(2)}%)
                          </span>
                        </div>
                        <div className="flex items-center justify-end gap-1 text-amber-400 text-xs mt-1">
                          {'★'.repeat(pick.stars)}
                          <span className="text-[10.5px] font-mono text-slate-400 ml-1">({pick.conviction_pct}%)</span>
                        </div>
                      </div>

                      <button
                        onClick={() => handlePaperTrade(pick)}
                        disabled={paperBuying[pick.symbol] || paperBought[pick.symbol]}
                        title="Add this delivery stock to Paper Trade at current price"
                        className={`p-2 rounded-xl border flex items-center justify-center transition-all shadow-md shrink-0 ${
                          paperBought[pick.symbol]
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400/50 shadow-emerald-600/30 active:scale-95'
                        }`}
                      >
                        {paperBought[pick.symbol] ? (
                          <Check className="w-4 h-4 text-emerald-400" />
                        ) : paperBuying[pick.symbol] ? (
                          <Zap className="w-4 h-4 animate-spin" />
                        ) : (
                          <Plus className="w-4 h-4 stroke-[2.5]" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* EXECUTION PLAN: WHEN TO BUY & WHEN TO EXIT */}
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {/* WHEN TO BUY */}
                    <div className="p-3 rounded-xl bg-slate-950 border border-emerald-500/30 space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-bold text-emerald-400 uppercase tracking-wider">
                        <span className="flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> When To Buy (Zone)
                        </span>
                        <span className="text-[9.5px] font-mono bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 rounded">
                          CNC / DELIVERY
                        </span>
                      </div>
                      <div className="text-sm font-mono font-bold text-white">
                        {pick.buy_zone_str}
                      </div>
                      <p className="text-[10.5px] text-slate-400 leading-tight">
                        Accumulate near lower boundary of the zone. Ideal entry on any 1-2 day minor dip.
                      </p>
                    </div>

                    {/* WHEN TO EXIT */}
                    <div className="p-3 rounded-xl bg-slate-950 border border-rose-500/30 space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-bold text-rose-400 uppercase tracking-wider">
                        <span className="flex items-center gap-1">
                          <Target className="w-3.5 h-3.5" /> When To Exit
                        </span>
                        <span className="text-[9.5px] font-mono bg-rose-500/20 text-rose-300 px-1.5 py-0.2 rounded">
                          TARGETS & SL
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-center font-mono text-xs">
                        <div className="bg-rose-500/10 p-1 rounded border border-rose-500/20">
                          <div className="text-[9px] text-rose-400">SL</div>
                          <div className="font-bold text-white">₹{Number(pick.stop_loss || 0).toFixed(2)}</div>
                          <div className="text-[8.5px] text-rose-400">-{pick.stop_loss_risk_pct}%</div>
                        </div>
                        <div className="bg-emerald-500/10 p-1 rounded border border-emerald-500/20">
                          <div className="text-[9px] text-emerald-400">Target 1</div>
                          <div className="font-bold text-white">₹{Number(pick.target_1 || 0).toFixed(2)}</div>
                          <div className="text-[8.5px] text-emerald-300">+{pick.target_1_gain_pct}%</div>
                        </div>
                        <div className="bg-cyan-500/10 p-1 rounded border border-cyan-500/20">
                          <div className="text-[9px] text-cyan-400">Target 2</div>
                          <div className="font-bold text-white">₹{Number(pick.target_2 || 0).toFixed(2)}</div>
                          <div className="text-[8.5px] text-cyan-300">+{pick.target_2_gain_pct}%</div>
                        </div>
                      </div>
                      <div className="text-[10px] text-amber-400/90 leading-tight">
                        <strong>Rule:</strong> {pick.trailing_sl_rule}
                      </div>
                    </div>
                  </div>
                </div>

                {/* POSITION SIZING FOR CHOSEN BUDGET */}
                <div className="p-4 bg-slate-950/60 space-y-3">
                  <div className="bg-slate-900/80 rounded-xl p-3 border border-slate-800">
                    <div className="flex items-center justify-between text-[11px] font-bold text-slate-300 mb-2">
                      <span className="flex items-center gap-1.5 text-indigo-300">
                        <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                        Plan for ₹{Number(budget || 1000).toLocaleString('en-IN')} Budget (Delivery / Cash):
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        R:R <strong>1:{pick.risk_reward_ratio}</strong>
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-2 text-center font-mono">
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-slate-800">
                        <div className="text-xs font-bold text-white">{pick.suggested_shares} Shares</div>
                        <div className="text-[9px] text-slate-500">Buy Qty</div>
                      </div>
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-slate-800">
                        <div className="text-xs font-bold text-slate-300">₹{Number(pick.invested_amount || 0).toLocaleString('en-IN')}</div>
                        <div className="text-[9px] text-slate-500">Invested</div>
                      </div>
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-slate-800">
                        <div className="text-xs font-bold text-emerald-400">+₹{Number(pick.profit_target_1 || 0).toLocaleString('en-IN')}</div>
                        <div className="text-[9px] text-slate-500">Gain at Target 1</div>
                      </div>
                      <div className="bg-slate-950 p-1.5 rounded-lg border border-slate-800">
                        <div className="text-xs font-bold text-rose-400">-₹{Number(pick.max_loss_at_sl || 0).toLocaleString('en-IN')}</div>
                        <div className="text-[9px] text-slate-500">Max Risk at SL</div>
                      </div>
                    </div>
                  </div>

                  {/* Technical & Fundamental Catalysts */}
                  <div className="space-y-1.5 text-[11px] leading-relaxed text-slate-300">
                    <div>
                      <strong className="text-indigo-400">📈 Technical Setup:</strong> {pick.technical_setup}
                    </div>
                    <div>
                      <strong className="text-cyan-400">🏢 Fundamental Reason:</strong> {pick.fundamental_catalyst}
                    </div>
                  </div>

                  {/* Card Footer Actions */}
                  <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[10.5px] font-mono text-slate-500">
                      Risk Profile: <span className="text-slate-300 font-semibold">{pick.risk_profile.replace('_', ' ')}</span>
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handlePaperTrade(pick)}
                        disabled={paperBuying[pick.symbol] || paperBought[pick.symbol]}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all shadow-md ${
                          paperBought[pick.symbol]
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20'
                        }`}
                      >
                        {paperBought[pick.symbol] ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span>In Portfolio</span>
                          </>
                        ) : (
                          <>
                            <Plus className={`w-3.5 h-3.5 stroke-[2.5] ${paperBuying[pick.symbol] ? 'animate-spin' : ''}`} />
                            <span>{paperBuying[pick.symbol] ? 'Adding...' : '+ Add to Paper Trade'}</span>
                          </>
                        )}
                      </button>

                      <button
                        onClick={() => handleSendSingle(pick.symbol)}
                        disabled={isSingleSending || isSingleSent}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                          isSingleSent
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : 'bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30'
                        }`}
                      >
                        {isSingleSent ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Sent Alert</span>
                          </>
                        ) : (
                          <>
                            <Send className={`w-3.5 h-3.5 ${isSingleSending ? 'animate-pulse' : ''}`} />
                            <span>{isSingleSending ? 'Sending...' : 'Send Alert'}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
