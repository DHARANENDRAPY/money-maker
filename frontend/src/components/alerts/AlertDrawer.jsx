import React, { useState } from 'react';
import { X, Check, Bell, AlertTriangle, Info, CheckCircle2, ShieldAlert } from 'lucide-react';
import { useMarket } from '../../context/MarketContext';

export default function AlertDrawer() {
  const { isAlertDrawerOpen, setIsAlertDrawerOpen, alerts, handleDismissAlert } = useMarket();
  const [filter, setFilter] = useState('ALL'); // ALL, UNREAD, WARNING

  if (!isAlertDrawerOpen) return null;

  const filteredAlerts = alerts.filter(a => {
    if (filter === 'UNREAD') return !a.is_dismissed;
    if (filter === 'WARNING') return a.severity === 'WARNING' || a.severity === 'DANGER';
    return true;
  });

  const getSeverityIcon = (sev) => {
    switch (sev) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'WARNING':
      case 'DANGER':
        return <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />;
      default:
        return <Info className="w-4 h-4 text-cyan-400 shrink-0" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={() => setIsAlertDrawerOpen(false)}
      />

      <div className="absolute inset-y-0 right-0 max-w-md w-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col z-10">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Market Alert Center</h2>
              <p className="text-[11px] text-slate-400">Real-time setup signals & system events</p>
            </div>
          </div>
          <button
            onClick={() => setIsAlertDrawerOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter Pills */}
        <div className="px-4 py-2.5 border-b border-slate-800/60 bg-slate-950/40 flex items-center space-x-2 text-xs">
          {['ALL', 'UNREAD', 'WARNING'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                filter === f
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Alerts List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {filteredAlerts.length === 0 ? (
            <div className="text-center py-16 text-slate-500 text-xs">
              <Check className="w-8 h-8 mx-auto mb-2 text-slate-600" />
              <p>No active alerts matching filter.</p>
            </div>
          ) : (
            filteredAlerts.map((a) => (
              <div
                key={a.alert_id}
                className={`p-3.5 rounded-xl border transition-all ${
                  a.is_dismissed
                    ? 'bg-slate-950/40 border-slate-800/40 opacity-60'
                    : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    {getSeverityIcon(a.severity)}
                    <h3 className="text-xs font-semibold text-slate-200">
                      {a.symbol && <span className="font-mono text-cyan-400 mr-1.5">[{a.symbol}]</span>}
                      {a.title}
                    </h3>
                  </div>
                  {!a.is_dismissed && (
                    <button
                      onClick={() => handleDismissAlert(a.alert_id)}
                      className="text-[10px] text-slate-400 hover:text-cyan-400 shrink-0 p-1 rounded hover:bg-slate-800"
                      title="Dismiss"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                <p className="text-[11.5px] text-slate-300 mt-2 leading-relaxed">
                  {a.message}
                </p>

                {a.details && Object.keys(a.details).length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-slate-800/60 flex flex-wrap gap-2 text-[10px] font-mono text-slate-400">
                    {Object.entries(a.details).map(([k, v]) => (
                      <span key={k} className="bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                        {k}: <span className="text-slate-200">{typeof v === 'number' ? v : String(v)}</span>
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-2 text-[10px] text-slate-500 font-mono">
                  {(() => {
                    try {
                      let s = String(a.timestamp || '').trim();
                      if (!s.endsWith('Z') && !s.includes('+') && !/[-+]\d{2}:\d{2}$/.test(s)) s = s.replace(' ', 'T') + 'Z';
                      const d = new Date(s);
                      return isNaN(d.getTime()) ? a.timestamp : d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
                    } catch {
                      return a.timestamp;
                    }
                  })()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
