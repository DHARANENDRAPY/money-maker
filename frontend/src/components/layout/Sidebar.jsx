import { 
  Target,
  PackageCheck,
  Wallet,
  History,
  TrendingUp,
  ShieldAlert,
  Settings
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';

const navItems = [
  { id: 'recommendations', label: 'Intraday Picks', icon: Target, badge: '⚡ MIS' },
  { id: 'delivery', label: 'Delivery & Swing', icon: PackageCheck, badge: '💎 CNC' },
  { id: 'paper', label: 'Paper Trading', icon: Wallet, badge: '🎮 Live' },
  { id: 'history', label: 'All Recommendations', icon: History, badge: '📜 Vault' },
  { id: 'settings', label: 'Broker & Settings', icon: Settings, badge: '⚙️ API' },
];

export default function Sidebar() {
  const { activeTab, setActiveTab, isLiveWsConnected, overview, setIsPaperDrawerOpen, paperPortfolio } = useMarket();

  const pnl = paperPortfolio?.total_pnl ?? 0;
  const isProfit = pnl >= 0;

  return (
    <aside className="hidden md:flex w-64 bg-slate-900/90 border-r border-slate-800/80 flex-col justify-between shrink-0 select-none z-20 backdrop-blur-md">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5">
                Trade Intel <span className="text-cyan-400 font-mono text-xs px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/50">AI</span>
              </h1>
              <p className="text-[11px] text-slate-400 font-medium">NSE Intraday Terminal</p>
            </div>
          </div>
        </div>

        {/* Live Status indicator */}
        <div className="px-4 py-3 mx-3 my-3 rounded-lg bg-slate-950/60 border border-slate-800/60 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <span className={`w-2 h-2 rounded-full ${isLiveWsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
            <span className="text-slate-300 font-mono text-[11px]">
              {overview?.data_source === 'ANGEL_ONE_SMARTAPI' ? 'Angel One Live' : 'Broker Offline'}
            </span>
          </div>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
            {overview?.nifty50 ? `${overview.nifty50.change_pct > 0 ? '+' : ''}${overview.nifty50.change_pct}%` : 'NSE'}
          </span>
        </div>

        {/* Navigation list */}
        <nav className="px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 font-semibold shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                    isActive ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-800 text-slate-400'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div>
        {/* Paper Trading Portfolio Quick Button */}
        <div className="px-3 pb-1.5">
          <button
            onClick={() => setIsPaperDrawerOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-gradient-to-r from-emerald-950/70 to-slate-900 border border-emerald-500/30 hover:border-emerald-500/50 text-xs font-semibold text-white transition-all shadow-md group"
          >
            <span className="flex items-center gap-2">
              <Wallet className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
              <span>Paper Portfolio</span>
            </span>
            <span className={`font-mono text-[11px] font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfit ? '+' : ''}₹{Math.round(pnl)}
            </span>
          </button>
        </div>

        {/* Footer / Safety Disclaimer */}
        <div className="p-3.5 m-3 rounded-xl bg-slate-950/80 border border-slate-800/80 text-[11px] text-slate-400 space-y-1">
        <div className="flex items-center space-x-1.5 text-amber-400 font-semibold text-[10px] uppercase tracking-wider">
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Analysis Only</span>
        </div>
        <p className="text-[10.5px] leading-relaxed text-slate-400">
          No automated execution. Execute trades manually in your broker terminal.
        </p>
      </div>
      </div>
    </aside>
  );
}
