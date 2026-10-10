import React, { useState, useEffect } from 'react';
import { 
  ScanSearch, 
  Search, 
  Filter, 
  Star, 
  ArrowUpDown, 
  TrendingUp, 
  TrendingDown, 
  ExternalLink, 
  ShieldCheck,
  Zap,
  RefreshCw
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { fetchScanner } from '../../services/api';
import { getSmartInterval } from '../../utils/marketHours';

export default function ScannerPage() {
  const { setSelectedSymbol, setActiveTab, watchlist, toggleWatchlistSymbol, liveQuotes } = useMarket();
  const [scannerItems, setScannerItems] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSector, setSelectedSector] = useState('');
  const [selectedSetup, setSelectedSetup] = useState('');
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [sortField, setSortField] = useState('rel_volume');
  const [sortDirection, setSortDirection] = useState('desc');

  const loadScannerData = async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const data = await fetchScanner({
        sector: selectedSector || null,
        setup_type: selectedSetup || null,
        watchlist_only: watchlistOnly,
        search: searchTerm || null
      });
      setScannerItems(data.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadScannerData(true);
    // Smart refresh: 5s live market, 3min closed (scanner data is static outside hours)
    const ms = getSmartInterval(5000, 3 * 60000, 10 * 60000);
    const interval = setInterval(() => loadScannerData(false), ms);
    return () => clearInterval(interval);
  }, [selectedSector, selectedSetup, watchlistOnly, searchTerm]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  // Overlay live WebSocket ticks on scanner items
  const dynamicItems = scannerItems.map(item => {
    const live = liveQuotes?.[item.symbol];
    if (live) {
      return {
        ...item,
        ltp: live.ltp ?? item.ltp,
        change: live.change ?? item.change,
        change_pct: live.change_pct ?? item.change_pct,
        volume: live.volume ?? item.volume,
        high: live.high ?? item.high,
        low: live.low ?? item.low,
        vwap: live.vwap ?? item.vwap,
      };
    }
    return item;
  });

  const sortedItems = [...dynamicItems].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];
    if (valA === null || valA === undefined) valA = -9999;
    if (valB === null || valB === undefined) valB = -9999;
    if (typeof valA === 'string') {
      return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return sortDirection === 'asc' ? valA - valB : valB - valA;
  });

  const handleRowClick = (symbol) => {
    setSelectedSymbol(symbol);
    setActiveTab('analysis');
  };

  const sectors = Array.from(new Set(scannerItems.map(i => i.sector))).filter(Boolean);
  const setups = ['15m ORB Breakout', '15m ORB Breakdown', 'VWAP Trend Pullback', 'Mean Reversion'];

  return (
    <div className="p-6 space-y-5 max-w-7xl mx-auto">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <ScanSearch className="w-5 h-5 text-cyan-400" />
            NSE Market Scanner
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time screening of 12 market factors, volatility ranges, and high-probability setups.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={loadScannerData}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
            <span>Scan</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800/80 shadow-md grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search Symbol / Name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>

        {/* Sector Filter */}
        <select
          value={selectedSector}
          onChange={(e) => setSelectedSector(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All Sectors</option>
          {sectors.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Setup Filter */}
        <select
          value={selectedSetup}
          onChange={(e) => setSelectedSetup(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All Setups</option>
          {setups.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Watchlist Toggle */}
        <button
          onClick={() => setWatchlistOnly(!watchlistOnly)}
          className={`px-4 py-2 rounded-lg border font-medium flex items-center justify-center space-x-2 transition-colors ${
            watchlistOnly
              ? 'bg-amber-500/15 text-amber-300 border-amber-500/40'
              : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-white'
          }`}
        >
          <Star className={`w-3.5 h-3.5 ${watchlistOnly ? 'fill-amber-400 text-amber-400' : ''}`} />
          <span>Watchlist Only ({watchlist.length})</span>
        </button>
      </div>

      {/* Scanner Table */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800/80 text-slate-400 font-mono text-[11px] uppercase tracking-wider">
              <tr>
                <th className="p-3.5 w-10 text-center">★</th>
                <th className="p-3.5 cursor-pointer hover:text-white" onClick={() => handleSort('symbol')}>
                  <div className="flex items-center space-x-1">
                    <span>Symbol</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="p-3.5 cursor-pointer hover:text-white text-right" onClick={() => handleSort('ltp')}>
                  <div className="flex items-center justify-end space-x-1">
                    <span>LTP (₹)</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="p-3.5 cursor-pointer hover:text-white text-right" onClick={() => handleSort('change_pct')}>
                  <div className="flex items-center justify-end space-x-1">
                    <span>Change %</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="p-3.5 cursor-pointer hover:text-white text-right" onClick={() => handleSort('rel_volume')}>
                  <div className="flex items-center justify-end space-x-1">
                    <span>RVOL</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="p-3.5">Sector</th>
                <th className="p-3.5">Trend Bias</th>
                <th className="p-3.5">Detected Setup</th>
                <th className="p-3.5 cursor-pointer hover:text-white text-center" onClick={() => handleSort('ml_probability')}>
                  <div className="flex items-center justify-center space-x-1">
                    <span>Target Prob</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="p-3.5 text-center">R : R</th>
                <th className="p-3.5 text-center">Liquidity</th>
                <th className="p-3.5 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {sortedItems.length === 0 ? (
                <tr>
                  <td colSpan="12" className="text-center py-16 text-slate-500">
                    No stocks matching the selected criteria.
                  </td>
                </tr>
              ) : (
                sortedItems.map((item) => {
                  const isWatch = watchlist.includes(item.symbol);
                  const isPos = item.change_pct >= 0;
                  const hasSetup = item.setup_type && item.setup_type !== 'No Setup';
                  
                  return (
                    <tr
                      key={item.symbol}
                      className="hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      onClick={() => handleRowClick(item.symbol)}
                    >
                      {/* Watchlist Star */}
                      <td className="p-3.5 text-center" onClick={(e) => { e.stopPropagation(); toggleWatchlistSymbol(item.symbol); }}>
                        <button className="text-slate-600 hover:text-amber-400">
                          <Star className={`w-3.5 h-3.5 ${isWatch ? 'fill-amber-400 text-amber-400' : ''}`} />
                        </button>
                      </td>

                      {/* Symbol & Name */}
                      <td className="p-3.5">
                        <div className="font-mono font-bold text-white group-hover:text-cyan-400 transition-colors flex items-center gap-1.5">
                          {item.symbol}
                          {hasSetup && (
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping"></span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 truncate max-w-[120px]">{item.name}</div>
                      </td>

                      {/* LTP */}
                      <td className="p-3.5 text-right font-mono font-bold text-white">
                        ₹{item.ltp.toFixed(2)}
                      </td>

                      {/* Change % */}
                      <td className="p-3.5 text-right font-mono font-bold">
                        <span className={`px-2 py-0.5 rounded text-[11px] ${
                          isPos ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                        }`}>
                          {isPos ? '+' : ''}{item.change_pct.toFixed(2)}%
                        </span>
                      </td>

                      {/* RVOL */}
                      <td className="p-3.5 text-right font-mono">
                        <span className={`font-bold ${
                          item.rel_volume >= 2.0 ? 'text-amber-400' : (item.rel_volume >= 1.2 ? 'text-cyan-400' : 'text-slate-400')
                        }`}>
                          {item.rel_volume.toFixed(1)}x
                        </span>
                      </td>

                      {/* Sector */}
                      <td className="p-3.5 text-slate-300">
                        <span className="text-[11px] px-2 py-0.5 rounded bg-slate-950 border border-slate-800/80">
                          {item.sector}
                        </span>
                      </td>

                      {/* Trend Alignment */}
                      <td className="p-3.5">
                        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                          item.trend_alignment.includes('BULLISH')
                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            : (item.trend_alignment.includes('BEARISH')
                                ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                                : 'bg-slate-800 text-slate-400')
                        }`}>
                          {item.trend_alignment.replace('_', ' ')}
                        </span>
                      </td>

                      {/* Setup Type */}
                      <td className="p-3.5">
                        {hasSetup ? (
                          <div className="flex items-center space-x-1.5 text-cyan-300 font-semibold">
                            <Zap className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                            <span>{item.setup_type}</span>
                          </div>
                        ) : (
                          <span className="text-slate-500 text-[11px]">No Setup</span>
                        )}
                      </td>

                      {/* ML Target Prob */}
                      <td className="p-3.5 text-center font-mono font-bold">
                        {item.ml_probability ? (
                          <span className={`px-2 py-0.5 rounded text-[11px] ${
                            item.ml_probability >= 0.60
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                              : 'bg-slate-800 text-slate-300'
                          }`}>
                            {Math.round(item.ml_probability * 100)}%
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>

                      {/* Risk Reward */}
                      <td className="p-3.5 text-center font-mono text-slate-300 font-semibold">
                        {item.risk_reward ? `1 : ${item.risk_reward.toFixed(1)}` : '—'}
                      </td>

                      {/* Liquidity */}
                      <td className="p-3.5 text-center font-mono">
                        <div className="flex items-center justify-center space-x-1">
                          <span className="text-slate-300 text-[11px]">{Math.round(item.liquidity_score)}</span>
                          <div className="w-8 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div 
                              style={{ width: `${item.liquidity_score}%` }} 
                              className="h-full bg-cyan-400 rounded-full"
                            />
                          </div>
                        </div>
                      </td>

                      {/* Action */}
                      <td className="p-3.5 text-center">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleRowClick(item.symbol); }}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-cyan-600 hover:text-white text-cyan-400 transition-colors text-[11px] flex items-center gap-1 mx-auto"
                        >
                          <span>Analyze</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
