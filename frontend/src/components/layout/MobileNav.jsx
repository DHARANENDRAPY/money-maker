import React from 'react';
import { useMarket } from '../../context/MarketContext';
import { LayoutDashboard, Target, PackageCheck, Flame, Menu } from 'lucide-react';

const mobileNavItems = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'recommendations', label: 'Intraday', icon: Target },
  { id: 'delivery', label: 'Swing', icon: PackageCheck },
  { id: 'options', label: 'Options', icon: Flame },
];

export default function MobileNav() {
  const { activeTab, setActiveTab } = useMarket();

  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 z-30 pb-safe">
      <div className="flex justify-around items-center h-16">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-cyan-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </button>
          );
        })}
        {/* Settings / More button */}
        <button
          onClick={() => setActiveTab('settings')}
          className={`flex flex-col items-center justify-center w-full h-full space-y-1 ${
            activeTab === 'settings' ? 'text-cyan-400' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Menu className="w-5 h-5" />
          <span className="text-[10px] font-medium">Menu</span>
        </button>
      </div>
    </div>
  );
}
