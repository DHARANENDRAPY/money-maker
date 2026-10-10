import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  Calculator, 
  AlertTriangle, 
  DollarSign, 
  Percent, 
  Layers, 
  ArrowRight,
  Receipt,
  Scale
} from 'lucide-react';
import { useMarket } from '../../context/MarketContext';
import { calculateRisk } from '../../services/api';

export default function RiskAnalyticsPage() {
  const { selectedSymbol } = useMarket();
  
  // State inputs
  const [symbol, setSymbol] = useState(selectedSymbol || 'RELIANCE');
  const [capital, setCapital] = useState(100000);
  const [riskPct, setRiskPct] = useState(1.0);
  const [entryPrice, setEntryPrice] = useState(2940.0);
  const [stopLoss, setStopLoss] = useState(2925.0);
  const [targetPrice, setTargetPrice] = useState(2970.0);
  const [direction, setDirection] = useState('LONG');
  const [brokerageType, setBrokerageType] = useState('FLAT');
  
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const runCalculation = async () => {
    setIsLoading(true);
    try {
      const res = await calculateRisk({
        symbol,
        capital: Number(capital),
        risk_pct: Number(riskPct),
        entry_price: Number(entryPrice),
        stop_loss: Number(stopLoss),
        target_price: Number(targetPrice),
        direction,
        brokerage_type: brokerageType
      });
      setResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    runCalculation();
  }, [symbol, capital, riskPct, entryPrice, stopLoss, targetPrice, direction, brokerageType]);

  const charges = result?.charges_breakdown;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-cyan-400" />
          Indian Equity Intraday Risk & Statutory Charges Calculator
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Exact position sizing, risk budgeting, STT, Stamp Duty, GST, Exchange charges, and breakeven point calculation.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Input Form */}
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 shadow-xl space-y-4">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5 border-b border-slate-800 pb-3">
            <Calculator className="w-4 h-4 text-cyan-400" />
            Trade & Risk Parameters
          </h2>

          <div className="space-y-3.5 text-xs">
            {/* Symbol & Direction */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-400 font-semibold block mb-1">Symbol</label>
                <input
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono font-bold focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-semibold block mb-1">Direction</label>
                <div className="grid grid-cols-2 gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                  <button
                    onClick={() => setDirection('LONG')}
                    className={`py-1 rounded text-xs font-bold font-mono transition-colors ${
                      direction === 'LONG' ? 'bg-emerald-500 text-white shadow' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    LONG
                  </button>
                  <button
                    onClick={() => setDirection('SHORT')}
                    className={`py-1 rounded text-xs font-bold font-mono transition-colors ${
                      direction === 'SHORT' ? 'bg-rose-500 text-white shadow' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    SHORT
                  </button>
                </div>
              </div>
            </div>

            {/* Total Capital & Risk % */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-400 font-semibold block mb-1">Trading Capital (₹)</label>
                <input
                  type="number"
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 font-semibold block mb-1">Max Risk Per Trade (%)</label>
                <input
                  type="number"
                  step="0.25"
                  value={riskPct}
                  onChange={(e) => setRiskPct(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-cyan-400 font-mono font-bold focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            {/* Entry, Stop Loss, Target */}
            <div className="space-y-3 pt-2 border-t border-slate-800/80">
              <div>
                <label className="text-[11px] text-slate-400 font-semibold block mb-1">Planned Entry Price (₹)</label>
                <input
                  type="number"
                  step="0.05"
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono font-bold focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[11px] text-rose-400 font-semibold block mb-1">Planned Stop-Loss (₹)</label>
                <input
                  type="number"
                  step="0.05"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-rose-900/60 rounded-lg px-3 py-2 text-rose-300 font-mono font-bold focus:outline-none focus:border-rose-500"
                />
              </div>

              <div>
                <label className="text-[11px] text-emerald-400 font-semibold block mb-1">Planned Target Price (₹)</label>
                <input
                  type="number"
                  step="0.05"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-emerald-900/60 rounded-lg px-3 py-2 text-emerald-300 font-mono font-bold focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right 2 Columns: Position Sizing & Indian Statutory Charges Breakdown */}
        <div className="lg:col-span-2 space-y-6">
          {/* Position Sizing Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[10.5px] text-slate-400 uppercase tracking-wider font-semibold">Max Risk Cap</div>
              <div className="font-mono text-xl font-bold text-rose-400 mt-1">
                ₹{result?.max_risk_amount?.toFixed(2) || '0.00'}
              </div>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">{riskPct}% of Capital</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[10.5px] text-slate-400 uppercase tracking-wider font-semibold">Optimal Quantity</div>
              <div className="font-mono text-xl font-bold text-cyan-300 mt-1">
                {result?.capped_quantity || 0} <span className="text-xs text-slate-400 font-normal">Shares</span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">Capital: ₹{result?.total_capital_required?.toLocaleString('en-IN')}</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[10.5px] text-slate-400 uppercase tracking-wider font-semibold">Net P&amp;L @ Stop</div>
              <div className="font-mono text-xl font-bold text-rose-400 mt-1">
                -₹{Math.abs(result?.net_loss_at_stop ?? 0).toFixed(2)}
              </div>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">Incl. all taxes</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[10.5px] text-slate-400 uppercase tracking-wider font-semibold">Net P&amp;L @ Target</div>
              <div className="font-mono text-xl font-bold text-emerald-400 mt-1">
                +₹{(result?.net_profit_at_target ?? 0).toFixed(2)}
              </div>
              <div className="text-[10px] text-slate-400 font-mono mt-0.5">Incl. all taxes</div>
            </div>
          </div>

          {/* Risk Warning Alert if Any */}
          {result?.risk_warning && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/60 text-xs text-amber-300 flex items-center space-x-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{result.risk_warning}</span>
            </div>
          )}

          {/* Detailed Indian Statutory Charges Breakdown Table */}
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Receipt className="w-4 h-4 text-cyan-400" />
                NSE Equity Intraday Statutory Charges Breakdown
              </h3>
              <span className="text-[11px] font-mono text-slate-400">
                Turnover: ₹{charges?.turnover?.toLocaleString('en-IN') || '0.00'}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs font-mono">
              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40">
                <span className="text-slate-400 text-[10.5px] block">Brokerage (Buy + Sell)</span>
                <span className="text-white font-bold text-sm">₹{charges?.brokerage?.toFixed(2)}</span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40">
                <span className="text-slate-400 text-[10.5px] block">STT (0.025% on Sell)</span>
                <span className="text-white font-bold text-sm">₹{charges?.stt?.toFixed(2)}</span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40">
                <span className="text-slate-400 text-[10.5px] block">Exchange Txn (0.00297%)</span>
                <span className="text-white font-bold text-sm">₹{charges?.exchange_txn_charge?.toFixed(2)}</span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40">
                <span className="text-slate-400 text-[10.5px] block">GST (18% on Charges)</span>
                <span className="text-white font-bold text-sm">₹{charges?.gst?.toFixed(2)}</span>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/40">
                <span className="text-slate-400 text-[10.5px] block">Stamp Duty (0.003% Buy)</span>
                <span className="text-white font-bold text-sm">₹{charges?.stamp_duty?.toFixed(2)}</span>
              </div>

              <div className="p-2.5 rounded-lg bg-cyan-950/40 border border-cyan-800/50">
                <span className="text-cyan-400 text-[10.5px] block font-bold">Total Statutory Costs</span>
                <span className="text-cyan-300 font-bold text-sm">₹{charges?.total_charges?.toFixed(2)}</span>
              </div>
            </div>

            {/* Breakeven Points Callout */}
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">Points Movement Required for Breakeven:</span>
              <span className="text-amber-400 font-bold text-sm">₹{charges?.breakeven_points?.toFixed(2)} per share</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
