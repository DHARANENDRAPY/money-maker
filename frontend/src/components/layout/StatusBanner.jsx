import React from 'react';
import { Info, AlertTriangle, ShieldCheck, ArrowRight } from 'lucide-react';
import { useMarket } from '../../context/MarketContext';

export default function StatusBanner() {
  const { overview, setActiveTab } = useMarket();
  const isDemo = overview?.data_source !== 'ANGEL_ONE_SMARTAPI';

  if (!isDemo) {
    return (
      <div className="bg-emerald-950/40 border-b border-emerald-800/40 px-6 py-1.5 flex items-center justify-between text-xs text-emerald-300">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span><strong>Live Broker Feed Connected:</strong> Real-time tick stream active from Angel One SmartAPI. Analysis only.</span>
        </div>
        <span className="font-mono text-[11px] bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-700/50">LIVE DATA</span>
      </div>
    );
  }

  return (
    <div className="bg-rose-950/40 border-b border-rose-800/40 px-6 py-1.5 flex items-center justify-between text-xs text-rose-200">
      <div className="flex items-center space-x-2">
        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
        <span>
          <strong>Live Market Feed Offline:</strong> Angel One SmartAPI is not connected. Enter your broker credentials to stream real-time NSE market quotes.
        </span>
      </div>
      <button
        onClick={() => setActiveTab('settings')}
        className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 font-medium underline underline-offset-2 ml-4 text-[11px] shrink-0"
      >
        <span>Connect Angel One API</span>
        <ArrowRight className="w-3 h-3" />
      </button>
    </div>
  );
}
