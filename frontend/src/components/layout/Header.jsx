import React, { useState, useEffect } from 'react';
import { 
  Bell, RefreshCw, Radio, Sparkles, Clock, AlertTriangle,
  Volume2, VolumeX, Eye, Layers, Wallet, Zap
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';

export default function Header() {
  const { 
    overview, 
    unreadAlertsCount, 
    setIsAlertDrawerOpen, 
    refreshOverview, 
    isLiveWsConnected, 
    lastTick,
    uiMode,
    toggleUiMode,
    isAudioMuted,
    toggleAudio,
    isMasterFeedActive,
    toggleMasterFeed,
    paperPortfolio,
    setIsPaperDrawerOpen
  } = useMarket();

  const [currentTime, setCurrentTime] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // Format as IST (UTC+5:30)
      const options = { timeZone: 'Asia/Kolkata', hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' };
      setCurrentTime(new Intl.DateTimeFormat('en-GB', options).format(now));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    await refreshOverview();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const nifty = lastTick?.nifty50 || overview?.nifty50;
  const banknifty = lastTick?.banknifty || overview?.banknifty;
  const paperPnl = paperPortfolio?.total_pnl ?? 0;
  const isPaperProfit = paperPnl >= 0;

  return (
    <header className="h-14 bg-slate-900/80 border-b border-slate-800/80 px-4 md:px-6 flex items-center justify-between shrink-0 select-none z-10 backdrop-blur-md">
      {/* Indices Ticker Bar */}
      <div className="flex items-center space-x-4 md:space-x-6 overflow-x-auto no-scrollbar py-1">
        {/* NIFTY 50 */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="font-semibold text-slate-300">NIFTY 50</span>
          <span className="font-mono font-medium text-slate-100">
            {nifty?.ltp ? nifty.ltp.toLocaleString('en-IN') : '--'}
          </span>
          <span className={`font-mono text-[10.5px] px-1.5 py-0.2 rounded font-semibold ${
            (nifty?.change_pct ?? 0) >= 0
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
              : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
          }`}>
            {nifty?.change_pct != null ? `${nifty.change_pct >= 0 ? '+' : ''}${nifty.change_pct}%` : '--'}
          </span>
        </div>

        <div className="h-4 w-[1px] bg-slate-800"></div>

        {/* BANK NIFTY */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="font-semibold text-slate-300">BANK NIFTY</span>
          <span className="font-mono font-medium text-slate-100">
            {banknifty?.ltp ? banknifty.ltp.toLocaleString('en-IN') : '--'}
          </span>
          <span className={`font-mono text-[10.5px] px-1.5 py-0.2 rounded font-semibold ${
            (banknifty?.change_pct ?? 0) >= 0
              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
              : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
          }`}>
            {banknifty?.change_pct != null ? `${banknifty.change_pct >= 0 ? '+' : ''}${banknifty.change_pct}%` : '--'}
          </span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-2.5 md:space-x-3">
        {/* Master Live Feed Toggle */}
        <button
          onClick={toggleMasterFeed}
          className={`hidden sm:flex px-2.5 py-1 rounded-lg text-[11px] font-mono font-bold items-center gap-1.5 transition-all border ${
            isMasterFeedActive
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/30 hover:bg-rose-500/20'
          }`}
          title={isMasterFeedActive ? 'Live API Feed Active. Click to pause.' : 'API Feed Paused. Click to start live data.'}
        >
          {isMasterFeedActive ? <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-400" /> : <Zap className="w-3.5 h-3.5 opacity-60" />}
          {isMasterFeedActive ? 'API LIVE' : 'API PAUSED'}
        </button>

        {/* Simple Mode vs Pro Mode Toggle */}
        <button
          onClick={toggleUiMode}
          className={`px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all border ${
            uiMode === 'simple'
              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 shadow-sm'
              : 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
          }`}
          title={uiMode === 'simple' ? 'Currently in Simple View. Click for Pro Quant View.' : 'Currently in Pro Quant View. Click for Simple View.'}
        >
          {uiMode === 'simple' ? <Eye className="w-3.5 h-3.5 text-emerald-400" /> : <Layers className="w-3.5 h-3.5 text-indigo-400" />}
          <span className="hidden sm:inline">{uiMode === 'simple' ? 'Simple View' : 'Pro View'}</span>
        </button>

        {/* Paper Trading Wallet Button */}
        <button
          onClick={() => setIsPaperDrawerOpen(true)}
          className="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-700/80 hover:border-emerald-500/40 text-xs font-mono font-medium flex items-center gap-1.5 transition-all text-slate-200"
          title="Open Paper Trading Portfolio"
        >
          <Wallet className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden sm:inline">Paper:</span>
          <span className={`font-bold ${isPaperProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isPaperProfit ? '+' : ''}₹{Math.round(paperPnl)}
          </span>
        </button>

        {/* Audio Sound Toggle */}
        <button
          onClick={toggleAudio}
          className={`p-2 rounded-lg border transition-colors ${
            !isAudioMuted
              ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
              : 'bg-slate-800/50 text-slate-500 border-slate-700/40 hover:text-slate-300'
          }`}
          title={isAudioMuted ? 'Audio alerts are muted. Click to enable sound.' : 'Audio alerts are active. Click to mute.'}
        >
          {isAudioMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>

        {/* Clock */}
        <div className="hidden lg:flex items-center space-x-1.5 text-xs text-slate-400 font-mono bg-slate-950/60 px-2.5 py-1 rounded-lg border border-slate-800/60">
          <Clock className="w-3.5 h-3.5 text-cyan-400" />
          <span>{currentTime || '09:30:00'} IST</span>
        </div>

        {/* Refresh button */}
        <button
          onClick={handleManualRefresh}
          className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors border border-slate-700/40"
          title="Refresh Market Snapshot"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
        </button>

        {/* Alert Bell */}
        <button
          onClick={() => setIsAlertDrawerOpen(true)}
          className="relative p-2 rounded-lg bg-slate-800/50 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors border border-slate-700/40"
          title="Market Alerts"
        >
          <Bell className="w-4 h-4" />
          {unreadAlertsCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse">
              {unreadAlertsCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}
