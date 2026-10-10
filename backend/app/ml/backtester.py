from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from app.engine.risk_calculator import calculate_indian_equity_intraday_charges
from app.engine.indicators import enrich_candles_with_indicators, detect_key_levels

class BacktestEngine:
    """
    Intraday Strategy Backtester with realistic slippage and Indian statutory transaction costs.
    Evaluates setups across historical intraday sessions.
    """

    @staticmethod
    def run_backtest(
        df_dict: Dict[str, pd.DataFrame],
        initial_capital: float = 100000.0,
        risk_per_trade_pct: float = 1.0,
        slippage_bps: float = 5.0,  # 0.05%
        brokerage_per_order: float = 20.0
    ) -> Dict[str, Any]:
        trades = []
        equity = initial_capital
        equity_curve = [{"trade_num": 0, "equity": initial_capital, "pnl": 0.0}]
        
        for symbol, df in df_dict.items():
            if df.empty or len(df) < 30:
                continue
                
            enriched = enrich_candles_with_indicators(df)
            levels = detect_key_levels(enriched)
            orb_h = levels.get("orb_high", 0)
            orb_l = levels.get("orb_low", 0)
            
            # Simulate through candles
            for i in range(15, len(enriched) - 5):
                row = enriched.iloc[i]
                prev = enriched.iloc[i-1]
                close = float(row['close'])
                high = float(row['high'])
                low = float(row['low'])
                vwap = float(row.get('vwap', close))
                atr = float(row.get('atr14', close * 0.01))
                rvol = float(row.get('rvol', 1.0))
                
                # Check for long ORB trigger
                if close > orb_h and prev['close'] <= orb_h and rvol > 1.2 and close > vwap:
                    entry = close * (1 + (slippage_bps / 10000.0))  # Apply entry slippage
                    sl = max(orb_h - (0.8 * atr), vwap - 0.5 * atr)
                    tp = entry + (1.8 * abs(entry - sl))
                    
                    risk_per_share = abs(entry - sl)
                    if risk_per_share <= 0:
                        continue
                        
                    max_risk_amount = equity * (risk_per_trade_pct / 100.0)
                    qty = int(max_risk_amount / risk_per_share)
                    if qty <= 0:
                        continue
                        
                    # Evaluate outcome over next 10 candles
                    exit_price = entry
                    outcome = "TIME_EXIT"
                    
                    for k in range(i + 1, min(i + 12, len(enriched))):
                        future_row = enriched.iloc[k]
                        f_h = float(future_row['high'])
                        f_l = float(future_row['low'])
                        
                        # Conservative stop hit
                        if f_h >= tp and f_l <= sl:
                            exit_price = sl * (1 - (slippage_bps / 10000.0))
                            outcome = "STOP_HIT"
                            break
                        elif f_l <= sl:
                            exit_price = sl * (1 - (slippage_bps / 10000.0))
                            outcome = "STOP_HIT"
                            break
                        elif f_h >= tp:
                            exit_price = tp * (1 - (slippage_bps / 10000.0))
                            outcome = "TARGET_HIT"
                            break
                    else:
                        exit_price = float(enriched.iloc[min(i + 11, len(enriched) - 1)]['close'])
                        
                    # Compute gross & statutory charges
                    gross_pnl = (exit_price - entry) * qty
                    charges = calculate_indian_equity_intraday_charges(
                        buy_price=entry,
                        sell_price=exit_price,
                        quantity=qty,
                        brokerage_type="FLAT",
                        flat_brokerage_rate=brokerage_per_order
                    )
                    net_pnl = gross_pnl - charges.total_charges
                    
                    equity += net_pnl
                    trades.append({
                        "symbol": symbol,
                        "entry": round(entry, 2),
                        "exit": round(exit_price, 2),
                        "stop_loss": round(sl, 2),
                        "target": round(tp, 2),
                        "quantity": qty,
                        "outcome": outcome,
                        "gross_pnl": round(gross_pnl, 2),
                        "charges": round(charges.total_charges, 2),
                        "net_pnl": round(net_pnl, 2),
                        "pnl_r": round(net_pnl / max_risk_amount, 2) if max_risk_amount > 0 else 0.0
                    })
                    
                    equity_curve.append({
                        "trade_num": len(trades),
                        "equity": round(equity, 2),
                        "pnl": round(net_pnl, 2)
                    })
                    
        # Compute summary metrics
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "net_pnl": 0.0,
                "max_drawdown_pct": 0.0,
                "trades": [],
                "equity_curve": equity_curve
            }
            
        winning_trades = [t for t in trades if t['net_pnl'] > 0]
        losing_trades = [t for t in trades if t['net_pnl'] <= 0]
        
        gross_profit = sum(t['net_pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['net_pnl'] for t in losing_trades)) if losing_trades else 1e-6
        
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0
        win_rate = round((len(winning_trades) / len(trades)) * 100.0, 1)
        total_net_pnl = round(equity - initial_capital, 2)
        
        # Max Drawdown
        equities = [pt['equity'] for pt in equity_curve]
        peak = equities[0]
        max_dd_pct = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            dd_pct = ((peak - eq) / peak) * 100.0 if peak > 0 else 0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                
        return {
            "initial_capital": initial_capital,
            "final_equity": round(equity, 2),
            "net_pnl": total_net_pnl,
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "trades": trades[-50:],  # Return latest 50 for display
            "equity_curve": equity_curve
        }
