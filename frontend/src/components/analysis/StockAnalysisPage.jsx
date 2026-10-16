import React, { useState, useEffect } from 'react';
import { 
  LineChart, 
  Sparkles, 
  ShieldCheck, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  MinusCircle, 
  Info, 
  Clock, 
  Layers, 
  Zap, 
  Calculator,
  Compass,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { fetchStockAnalysis } from '../../services/api';
import CandlestickChart from '../charts/CandlestickChart';

export default function StockAnalysisPage() {
  const { selectedSymbol, setSelectedSymbol, watchlist, setActiveTab, paperPortfolio } = useMarket();
  const [analysis, setAnalysis] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFactor, setSelectedFactor] = useState(null);

  const activeTrade = paperPortfolio?.open_positions?.find(p => p.symbol === selectedSymbol);

  const loadAnalysis = async (sym) => {
    setIsLoading(true);
    try {
      const data = await fetchStockAnalysis(sym || selectedSymbol || 'RELIANCE');
      setAnalysis(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAnalysis(selectedSymbol);
  }, [selectedSymbol]);

  const quote = analysis?.quote;
  const factors = analysis?.factors || [];
  const keyLevels = analysis?.key_levels || {};

  const getFactorStatusBadge = (status) => {
    switch (status) {
      case 'SUPPORTIVE':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">SUPPORTIVE</span>;
      case 'CONFLICTING':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">CONFLICTING</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">NEUTRAL</span>;
    }
  };

  const getScoreBar = (score) => {
    // Score from -1.0 to +1.0 -> 0% to 100%
    const norm = Math.round(((score + 1.0) / 2.0) * 100);
    return (
      <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden flex">
        <div 
          style={{ width: `${norm}%` }} 
          className={`h-full transition-all ${
            score > 0.2 ? 'bg-emerald-400' : (score < -0.2 ? 'bg-rose-400' : 'bg-slate-400')
          }`}
        />
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Symbol Selector & Summary Banner */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <select
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-white font-mono font-bold text-sm md:text-base px-3 py-1.5 rounded-xl focus:outline-none focus:border-cyan-500"
            >
              <optgroup label="⚡ Affordable & Budget Picks (< ₹150)">
                <option value="SUZLON">SUZLON (₹62 - Green Energy)</option>
                <option value="NHPC">NHPC (₹89 - Green Hydro)</option>
                <option value="IDFCFIRSTB">IDFCFIRSTB (₹78 - Banking)</option>
                <option value="PNB">PNB (₹108 - PSU Bank)</option>
                <option value="IOC">IOC (₹138 - Oil PSU)</option>
                <option value="ZOMATO">ZOMATO (₹218 - High Growth)</option>
                <option value="IRFC">IRFC (₹145 - Railway PSU)</option>
                <option value="BHEL">BHEL (₹245 - Heavy Eng)</option>
                <option value="GAIL">GAIL (₹185 - Gas Utility)</option>
                <option value="TATASTEEL">TATASTEEL (₹142 - Steel)</option>
                <option value="BEL">BEL (₹290 - Defence)</option>
              </optgroup>
              <optgroup label="🏛️ Core Bluechips & Large Caps">
                <option value="RELIANCE">RELIANCE (Oil & Conglomerate)</option>
                <option value="INFY">INFY (IT Services)</option>
                <option value="TCS">TCS (IT Major)</option>
                <option value="HDFCBANK">HDFCBANK (Private Bank)</option>
                <option value="ICICIBANK">ICICIBANK (Private Bank)</option>
                <option value="SBIN">SBIN (PSU Banking)</option>
                <option value="TATAMOTORS">TATAMOTORS (Auto / EV)</option>
                <option value="BHARTIARTL">BHARTIARTL (Telecom / 5G)</option>
                <option value="ITC">ITC (FMCG)</option>
                <option value="LT">LT (Infrastructure)</option>
                <option value="SUNPHARMA">SUNPHARMA (Pharma)</option>
                <option value="AXISBANK">AXISBANK (Banking)</option>
                <option value="MARUTI">MARUTI (Auto)</option>
                <option value="TITAN">TITAN (Consumer Retail)</option>
                <option value="NTPC">NTPC (Power PSU)</option>
                <option value="ONGC">ONGC (Oil Exploration)</option>
                <option value="COALINDIA">COALINDIA (Mining)</option>
              </optgroup>
            </select>
            <span className="text-sm font-semibold text-slate-300 hidden sm:inline">{quote?.name}</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono hidden sm:inline">
              {quote?.sector}
            </span>
          </div>

          <div className="flex items-center space-x-4 mt-2">
            <span className="font-mono text-2xl font-bold text-white">
              ₹{quote?.ltp ? quote.ltp.toFixed(2) : '0.00'}
            </span>
            <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
              (quote?.change_pct ?? 0) >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
            }`}>
              {(quote?.change_pct ?? 0) >= 0 ? '+' : ''}{quote?.change_pct?.toFixed(2)}% (₹{quote?.change?.toFixed(2)})
            </span>
            <span className="text-xs text-slate-400 font-mono">
              VWAP: <span className="text-cyan-400 font-bold">₹{quote?.vwap?.toFixed(2)}</span>
            </span>
            <span className="text-xs text-slate-400 font-mono">
              RVOL: <span className="text-amber-400 font-bold">{quote?.rel_volume?.toFixed(1)}x</span>
            </span>
          </div>
        </div>

        {/* Composite Decision Box */}
        <div className="flex items-center space-x-3 bg-slate-950/80 p-3.5 rounded-xl border border-slate-800">
          <div className="text-right">
            <div className="text-[10.5px] text-slate-400 uppercase tracking-wider font-semibold">Composite Bias</div>
            <div className={`font-mono text-base font-bold ${
              analysis?.composite_bias === 'LONG' ? 'text-emerald-400' : (analysis?.composite_bias === 'SHORT' ? 'text-rose-400' : 'text-amber-400')
            }`}>
              {analysis?.composite_bias || 'NO_TRADE'}
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              Confidence: <span className="text-cyan-400 font-bold">{Math.round((analysis?.confidence_score ?? 0.7) * 100)}%</span>
            </div>
          </div>

          <button
            onClick={() => setActiveTab('risk')}
            className="px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-md shadow-cyan-600/20"
          >
            <Calculator className="w-3.5 h-3.5" />
            <span>Size Trade</span>
          </button>
        </div>
      </div>

      {/* Active Position Overlay Banner */}
      {activeTrade && (
        <div className="bg-gradient-to-r from-cyan-950/60 to-emerald-950/60 border border-cyan-500/30 rounded-xl p-3 flex flex-wrap items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-white font-bold">LIVE POSITION ACTIVE:</span>
            <span className="text-cyan-300 font-semibold">{activeTrade.direction} ({activeTrade.shares} shares @ ₹{activeTrade.entry_price?.toFixed(2)})</span>
            {activeTrade.trailing_status && (
              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                {activeTrade.trailing_status.replace(/_/g, ' ')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-slate-300">
            <span>T1: <strong className="text-emerald-400">₹{activeTrade.target_1?.toFixed(2)}</strong></span>
            <span>T2: <strong className="text-amber-400">₹{activeTrade.target_2?.toFixed(2)}</strong></span>
            <span>SL: <strong className="text-rose-400">₹{activeTrade.stop_loss?.toFixed(2)}</strong></span>
          </div>
        </div>
      )}

      {/* Chart & Key Levels Section */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 space-y-3">
          <CandlestickChart
            candles={analysis?.candles || []}
            keyLevels={keyLevels}
            activeTrade={activeTrade}
            height={360}
            showVolume={true}
            showVwap={true}
            showEma={true}
          />
        </div>

        {/* Key Price Action Levels Card */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-cyan-400" />
              Key Intraday Levels
            </h3>

            <div className="space-y-2 text-xs font-mono">
              <div className="flex justify-between p-2 rounded bg-slate-950/60 border border-slate-800/40">
                <span className="text-rose-400 font-semibold">Resistance 2 (R2)</span>
                <span className="text-white font-bold">₹{keyLevels.resistance_2?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60 border border-slate-800/40">
                <span className="text-rose-400 font-semibold">Resistance 1 (R1)</span>
                <span className="text-white font-bold">₹{keyLevels.resistance_1?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-cyan-950/40 border border-cyan-800/40">
                <span className="text-cyan-400 font-semibold">15m ORB High</span>
                <span className="text-white font-bold">₹{keyLevels.orb_high?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-amber-950/40 border border-amber-800/40">
                <span className="text-amber-400 font-semibold">Pivot Point (PP)</span>
                <span className="text-white font-bold">₹{keyLevels.pivot?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-cyan-950/40 border border-cyan-800/40">
                <span className="text-cyan-400 font-semibold">15m ORB Low</span>
                <span className="text-white font-bold">₹{keyLevels.orb_low?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-950/60 border border-slate-800/40">
                <span className="text-emerald-400 font-semibold">Support 1 (S1)</span>
                <span className="text-white font-bold">₹{keyLevels.support_1?.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 pt-3 border-t border-slate-800 font-mono">
            Time of Day: {analysis?.time_of_day_context?.market_phase || 'Active'}
          </div>
        </div>
      </div>

      {/* 12 TRADING FACTORS BREAKDOWN */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              Comprehensive 12-Factor Multi-Dimensional Evaluation
            </h2>
            <p className="text-xs text-slate-400">
              Independent evaluation across macro, technical, volume, temporal, and discipline pillars.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
            {factors.filter(f => f.status === 'SUPPORTIVE').length} Supportive / {factors.filter(f => f.status === 'CONFLICTING').length} Conflicting
          </span>
        </div>

        {/* 12 Factor Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {factors.map((factor) => (
            <div
              key={factor.factor_id}
              onClick={() => setSelectedFactor(factor)}
              className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all hover:shadow-md cursor-pointer flex flex-col justify-between space-y-3"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono font-bold flex items-center justify-center">
                      {factor.factor_id}
                    </span>
                    <h3 className="text-xs font-bold text-white">{factor.name}</h3>
                  </div>
                  {getFactorStatusBadge(factor.status)}
                </div>

                <div className="text-[10px] text-slate-400 mt-1 font-mono uppercase tracking-wider">
                  {factor.category} • Weight: {factor.weight_desc}
                </div>

                <p className="text-xs text-slate-300 mt-2.5 leading-relaxed">
                  {factor.summary}
                </p>
              </div>

              {/* Score Bar & Numeric representation */}
              <div className="pt-2 border-t border-slate-800/60 space-y-1.5">
                <div className="flex justify-between text-[10px] font-mono text-slate-400">
                  <span>Factor Score</span>
                  <span className={`font-bold ${
                    factor.score > 0 ? 'text-emerald-400' : (factor.score < 0 ? 'text-rose-400' : 'text-slate-400')
                  }`}>
                    {factor.score > 0 ? '+' : ''}{factor.score.toFixed(2)}
                  </span>
                </div>
                {getScoreBar(factor.score)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
