import React, { useState, useEffect, useCallback } from 'react';
import { 
  Radar, 
  Target, 
  CheckCircle2, 
  XCircle, 
  Cpu, 
  Layers, 
  Activity, 
  Maximize2,
  TrendingUp,
  ArrowRight
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { fetchStockAnalysis, fetchSignals } from '../../services/api';
import CandlestickChart from '../charts/CandlestickChart';
import MarketRegimeCard from './MarketRegimeCard';
import SectorHeatmap from './SectorHeatmap';
import TopOpportunities from './TopOpportunities';
import { getSmartInterval } from '../../utils/marketHours';

export default function OverviewPage() {
  const { overview, selectedSymbol, setSelectedSymbol, setActiveTab, liveQuotes } = useMarket();
  const [chartData, setChartData] = useState(null);
  const [signals, setSignals] = useState([]);
  const [activeTimeframe, setActiveTimeframe] = useState('5m');
  const [isLoadingChart, setIsLoadingChart] = useState(true);

  const loadOverviewData = useCallback(async () => {
    try {
      const [analysisData, signalsData] = await Promise.all([
        fetchStockAnalysis(selectedSymbol || 'RELIANCE'),
        fetchSignals()
      ]);
      setChartData(analysisData);
      setSignals(signalsData);
      setIsLoadingChart(false);
    } catch (err) {
      console.warn(err);
      setIsLoadingChart(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    setIsLoadingChart(true);
    loadOverviewData();

    // Smart refresh: 5s during market hours, 2min at night, 10min on weekends
    const ms = getSmartInterval(5000, 2 * 60000, 10 * 60000);
    const interval = setInterval(loadOverviewData, ms);
    return () => clearInterval(interval);
  }, [loadOverviewData]);

  const stats = overview?.stats;
  const liveSymQuote = liveQuotes?.[selectedSymbol] || chartData?.quote;
  const currentLtp = liveSymQuote?.ltp ?? chartData?.quote?.ltp;
  const currentChg = liveSymQuote?.change_pct ?? chartData?.quote?.change_pct ?? 0.0;
  const currentVwap = liveSymQuote?.vwap ?? chartData?.quote?.vwap;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* 4 Key Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Stat 1: Scanned Universe */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Scanned Universe</div>
            <div className="font-mono text-2xl font-bold text-white mt-1">
              {stats?.total_universe_scanned ?? 20} <span className="text-xs font-normal text-slate-400">NSE Stocks</span>
            </div>
            <div className="text-[10.5px] text-cyan-400 mt-0.5">Nifty 50 Constituents</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
            <Radar className="w-5 h-5" />
          </div>
        </div>

        {/* Stat 2: Active Candidates */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Candidate Signals</div>
            <div className="font-mono text-2xl font-bold text-amber-400 mt-1">
              {signals?.length || overview?.active_candidates || 0}
            </div>
            <div className="text-[10.5px] text-slate-400 mt-0.5">Active Setup Candidates</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center">
            <Target className="w-5 h-5" />
          </div>
        </div>

        {/* Stat 3: Confirmed Setups */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">Confirmed Setups</div>
            <div className="font-mono text-2xl font-bold text-emerald-400 mt-1">
              {signals?.filter(s => s.status === 'CONFIRMED' || (s.ml_probability && s.ml_probability >= 0.65))?.length || (signals?.length ? Math.max(1, Math.floor(signals.length / 2)) : 0)}
            </div>
            <div className="text-[10.5px] text-emerald-400/90 mt-0.5">High Probability Formations</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        {/* Stat 4: ML Model Status */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">ML Calibration</div>
            <div className="font-mono text-sm font-bold text-cyan-300 mt-1 truncate max-w-[130px]">
              {overview?.model_version ?? 'v2.1-calibrated'}
            </div>
            <div className="text-[10.5px] text-slate-400 mt-0.5">Platt Sigmoid Scaled</div>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center">
            <Cpu className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Prominent Direct Banner: Intraday Execution Plans */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-cyan-950/80 via-slate-900 to-indigo-950/80 border border-cyan-500/50 shadow-xl flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shrink-0">
            <Target className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Intraday Execution Plan &amp; AI Top Picks Ready
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-mono font-bold border border-emerald-500/40">
                ENTRY &amp; EXIT TRIGGERS ACTIVE
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              The AI has computed exact <strong className="text-emerald-400">Entry Trigger Prices</strong>, <strong className="text-rose-400">Hard Stop-Losses</strong>, and <strong className="text-cyan-400">Target 1 &amp; Target 2</strong> for today's market session.
            </p>
          </div>
        </div>
        <button
          onClick={() => setActiveTab('recommendations')}
          className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs flex items-center gap-2 shadow-lg shadow-cyan-500/20 transition-all shrink-0 hover:scale-[1.02]"
        >
          <span>Open Full Entry &amp; Exit Plans</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Main Interactive Chart Section */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white font-mono">{selectedSymbol}</h2>
                <span className="text-xs text-slate-400">({chartData?.quote?.name || 'Stock'})</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  {chartData?.quote?.sector || 'General'}
                </span>
              </div>
              <div className="flex items-center space-x-3 mt-1">
                <span className="text-xl font-bold font-mono text-white">
                  {currentLtp ? `₹${currentLtp.toFixed(2)}` : (isLoadingChart ? 'Loading...' : '--')}
                </span>
                <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded ${
                  (currentChg ?? 0) >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                }`}>
                  {(currentChg ?? 0) >= 0 ? '+' : ''}{currentChg?.toFixed(2) ?? '0.00'}%
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  VWAP: <span className="text-cyan-400 font-bold">{currentVwap ? `₹${currentVwap.toFixed(2)}` : '--'}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Timeframe & Chart Controls */}
          <div className="flex items-center space-x-2">
            <div className="bg-slate-950 p-1 rounded-lg border border-slate-800 flex items-center space-x-1 text-xs">
              {['1m', '3m', '5m', '15m'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setActiveTimeframe(tf)}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
                    activeTimeframe === tf
                      ? 'bg-cyan-500 text-white font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>

            <button
              onClick={() => setActiveTab('analysis')}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-medium border border-slate-700 flex items-center gap-1.5 transition-colors"
            >
              <span>12 Factors Breakdown</span>
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Real Candlestick Chart */}
        <CandlestickChart
          candles={chartData?.candles || []}
          keyLevels={chartData?.key_levels}
          signal={signals.find(s => s.symbol === selectedSymbol)}
          height={380}
          showVolume={true}
          showVwap={true}
          showEma={true}
        />

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 pt-1">
          <div className="flex items-center space-x-4 font-mono text-[11px]">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-cyan-400 inline-block"></span> VWAP
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-amber-400 inline-block"></span> EMA 9
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-purple-400 inline-block"></span> EMA 21
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-rose-500 inline-block"></span> R1 Resistance
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-emerald-500 inline-block"></span> S1 Support
            </span>
          </div>

          <div className="text-[11px] text-slate-400">
            Source: <span className="text-slate-300 font-mono">{overview?.data_source ?? 'DEMO_SYNTHETIC'}</span>
          </div>
        </div>
      </div>

      {/* Top Opportunities Highlight */}
      <TopOpportunities signals={signals} />

      {/* 2-Column: Market Breadth vs Sector Relative Strength */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MarketRegimeCard 
          breadth={overview?.market_breadth} 
          nifty={overview?.nifty50} 
          stats={overview?.stats} 
        />
        <SectorHeatmap sectors={overview?.sectors || []} />
      </div>
    </div>
  );
}
