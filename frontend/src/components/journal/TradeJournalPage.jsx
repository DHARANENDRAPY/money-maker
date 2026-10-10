import React, { useState, useEffect } from 'react';
import { 
  BookOpen, 
  Plus, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  TrendingUp, 
  TrendingDown,
  X
} from 'lucide-react';
import { fetchJournal, addJournalEntry } from '../../services/api';
import { useMarket } from '../../context/MarketContext';

export default function TradeJournalPage() {
  const { showToast } = useMarket();
  const [journalData, setJournalData] = useState({ analytics: null, entries: [] });
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Form State
  const [symbol, setSymbol] = useState('INFY');
  const [direction, setDirection] = useState('LONG');
  const [plannedEntry, setPlannedEntry] = useState(1890.0);
  const [actualEntry, setActualEntry] = useState(1892.0);
  const [plannedSL, setPlannedSL] = useState(1878.0);
  const [actualSL, setActualSL] = useState(1878.0);
  const [plannedTarget, setPlannedTarget] = useState(1915.0);
  const [actualExit, setActualExit] = useState(1912.0);
  const [quantity, setQuantity] = useState(50);
  const [strategy, setStrategy] = useState('15m ORB Breakout');
  const [deviations, setDeviations] = useState([]);
  const [notes, setNotes] = useState('');

  const loadJournal = async () => {
    setIsLoading(true);
    try {
      const data = await fetchJournal();
      setJournalData(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadJournal();
  }, []);

  const handleToggleDeviation = (dev) => {
    if (deviations.includes(dev)) {
      setDeviations(deviations.filter(d => d !== dev));
    } else {
      setDeviations([...deviations, dev]);
    }
  };

  const handleSaveTrade = async (e) => {
    e.preventDefault();
    try {
      await addJournalEntry({
        symbol,
        direction,
        planned_entry: Number(plannedEntry),
        actual_entry: Number(actualEntry),
        planned_stop_loss: Number(plannedSL),
        actual_stop_loss: Number(actualSL),
        planned_target: Number(plannedTarget),
        actual_exit: actualExit ? Number(actualExit) : null,
        quantity: Number(quantity),
        setup_strategy: strategy,
        deviations,
        notes
      });
      showToast('Trade successfully logged into journal', 'success');
      setIsModalOpen(false);
      loadJournal();
    } catch (err) {
      console.error(err);
      showToast('Error saving trade journal record', 'error');
    }
  };

  const analytics = journalData.analytics;
  const entries = journalData.entries || [];

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-cyan-400" />
            Trader Discipline & Behavioral Trade Journal
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Evaluate plan adherence, detect revenge trading loops, and track risk execution fidelity.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs flex items-center gap-2 transition-all shadow-lg shadow-cyan-600/20"
        >
          <Plus className="w-4 h-4" />
          <span>Log Manual Trade</span>
        </button>
      </div>

      {/* Discipline Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Plan Adherence Rate</div>
          <div className="font-mono text-2xl font-bold text-emerald-400 mt-1">
            {analytics?.plan_adherence_rate ?? 100}%
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Target: &gt;90% adherence</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Discipline Score</div>
          <div className="font-mono text-2xl font-bold text-cyan-300 mt-1">
            {analytics?.avg_discipline_score ?? 100} / 100
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Behavioral quality index</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Revenge Trade Alerts</div>
          <div className="font-mono text-2xl font-bold text-amber-400 mt-1">
            {analytics?.revenge_trading_flags ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">&lt;15m rapid re-entries</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Disciplined Win Rate</div>
          <div className="font-mono text-2xl font-bold text-emerald-400 mt-1">
            {analytics?.win_rate_when_disciplined ?? 75}%
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">vs {analytics?.win_rate_when_deviated ?? 33}% when deviated</div>
        </div>
      </div>

      {/* Trade Log Table */}
      <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-slate-800/80 flex items-center justify-between">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider">Executed Trade History</h2>
          <span className="text-[11px] font-mono text-slate-400">Total: {entries.length} Trades</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800/80 text-slate-400 font-mono text-[11px] uppercase tracking-wider">
              <tr>
                <th className="p-3.5">Symbol</th>
                <th className="p-3.5">Direction</th>
                <th className="p-3.5">Strategy</th>
                <th className="p-3.5 text-right">Entry / Exit</th>
                <th className="p-3.5 text-right">Quantity</th>
                <th className="p-3.5 text-right">Net P&amp;L (₹)</th>
                <th className="p-3.5 text-center">Discipline</th>
                <th className="p-3.5">Deviations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium">
              {entries.length === 0 ? (
                <tr>
                  <td colSpan="8" className="text-center py-16 text-slate-500">
                    No manual trade journal records logged yet. Click 'Log Manual Trade' above.
                  </td>
                </tr>
              ) : (
                entries.map((trade) => {
                  const isPos = trade.net_pnl >= 0;
                  return (
                    <tr key={trade.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-3.5 font-mono font-bold text-white">
                        {trade.symbol}
                      </td>
                      <td className="p-3.5">
                        <span className={`px-2 py-0.5 rounded font-mono text-[10.5px] font-bold ${
                          trade.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {trade.direction}
                        </span>
                      </td>
                      <td className="p-3.5 text-slate-300">{trade.setup_strategy || 'Discretionary'}</td>
                      <td className="p-3.5 text-right font-mono">
                        <span className="text-white">₹{trade.actual_entry.toFixed(2)}</span>
                        {trade.actual_exit && (
                          <span className="text-slate-400 text-[10.5px] block">→ ₹{trade.actual_exit.toFixed(2)}</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right font-mono text-slate-200">{trade.quantity}</td>
                      <td className="p-3.5 text-right font-mono font-bold">
                        <span className={isPos ? 'text-emerald-400' : 'text-rose-400'}>
                          {isPos ? '+' : ''}₹{trade.net_pnl.toFixed(2)}
                        </span>
                      </td>
                      <td className="p-3.5 text-center font-mono">
                        <span className={`px-2 py-0.5 rounded text-[10.5px] font-bold ${
                          trade.followed_plan ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                        }`}>
                          {trade.followed_plan ? '100% Plan' : `${trade.discipline_score}% Score`}
                        </span>
                      </td>
                      <td className="p-3.5">
                        {trade.deviations && trade.deviations.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {trade.deviations.map((d, i) => (
                              <span key={i} className="text-[9.5px] px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800">
                                {d}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-emerald-400 text-[11px]">Clean Execution</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Log Trade Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-cyan-400" />
                Log Executed Trade Record
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveTrade} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Symbol</label>
                  <input
                    type="text"
                    required
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono font-bold focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Direction</label>
                  <select
                    value={direction}
                    onChange={(e) => setDirection(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none"
                  >
                    <option value="LONG">LONG</option>
                    <option value="SHORT">SHORT</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Actual Entry Price (₹)</label>
                  <input
                    type="number"
                    step="0.05"
                    required
                    value={actualEntry}
                    onChange={(e) => setActualEntry(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Actual Exit Price (₹)</label>
                  <input
                    type="number"
                    step="0.05"
                    required
                    value={actualExit}
                    onChange={(e) => setActualExit(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Actual Stop Loss (₹)</label>
                  <input
                    type="number"
                    step="0.05"
                    required
                    value={actualSL}
                    onChange={(e) => setActualSL(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-rose-300 font-mono focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">Quantity</label>
                  <input
                    type="number"
                    required
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none"
                  />
                </div>
              </div>

              {/* Deviations Checklist */}
              <div className="space-y-1.5 pt-2 border-t border-slate-800">
                <label className="text-[11px] text-slate-400 block font-semibold">Behavioral Deviations (If any)</label>
                <div className="grid grid-cols-2 gap-2">
                  {['CHASED_ENTRY', 'MOVED_STOP_LOSS', 'REVENGE_TRADE', 'OVERSIZED_POSITION'].map((d) => (
                    <button
                      type="button"
                      key={d}
                      onClick={() => handleToggleDeviation(d)}
                      className={`p-2 rounded-lg border text-left font-mono text-[10.5px] transition-colors ${
                        deviations.includes(d)
                          ? 'bg-rose-950/60 text-rose-300 border-rose-800'
                          : 'bg-slate-950 text-slate-400 border-slate-800'
                      }`}
                    >
                      {d.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-cyan-600 text-white hover:bg-cyan-500 font-semibold"
                >
                  Save Journal Entry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
