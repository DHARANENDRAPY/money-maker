import datetime
import uuid
import math
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.services.market_state import market_state
from app.engine.indicators import enrich_candles_with_indicators
from app.providers.universe import NSE_UNIVERSE

router = APIRouter(tags=["backtest"])


class BacktestRequest(BaseModel):
    symbol: str = Field("RELIANCE", description="NSE Stock Symbol")
    days: int = Field(30, description="Simulation lookback period in days (15 to 90)")
    timeframe: str = Field("5m", description="Candle timeframe: 5m or 1d")
    initial_capital: float = Field(100000.0, description="Initial virtual capital in INR")
    budget_per_trade: float = Field(10000.0, description="Capital allocated per simulated trade")
    strategy: str = Field("AI_ENSEMBLE", description="Strategy: AI_ENSEMBLE, INTRADAY_MOMENTUM, or SWING_DELIVERY")
    sl_multiplier: Optional[float] = Field(1.4, description="ATR multiple for Stop Loss")
    target_multiplier: Optional[float] = Field(1.8, description="ATR multiple for Target 1")
    runner_multiplier: Optional[float] = Field(3.2, description="ATR multiple for Target 2 Runner")


class OptimizeRequest(BaseModel):
    symbol: str = Field("RELIANCE", description="NSE Stock Symbol")
    days: int = Field(30, description="Simulation lookback period in days (15 to 90)")
    timeframe: str = Field("5m", description="Candle timeframe: 5m or 1d")
    initial_capital: float = Field(100000.0, description="Initial virtual capital in INR")
    budget_per_trade: float = Field(10000.0, description="Capital allocated per trade")


def _run_simulation_bars(
    bars: List[Dict[str, Any]],
    sym: str,
    initial_capital: float,
    budget: float,
    timeframe: str,
    sl_mult: float = 1.4,
    t1_mult: float = 1.8,
    t2_mult: float = 3.2,
    record_equity: bool = False
) -> Dict[str, Any]:
    capital = initial_capital
    peak_equity = capital
    max_drawdown_rupees = 0.0
    max_drawdown_pct = 0.0

    equity_curve = []
    trade_log = []
    active_pos = None

    for i in range(20, len(bars)):
        bar = bars[i]
        curr_price = float(bar.get("close", 0))
        high_price = float(bar.get("high", curr_price))
        low_price = float(bar.get("low", curr_price))
        bar_time = str(bar.get("timestamp", ""))

        if active_pos is not None:
            entry = active_pos["entry_price"]
            t1 = active_pos["target_1"]
            t2 = active_pos["target_2"]
            sl = active_pos["stop_loss"]
            shares = active_pos["shares"]
            is_long = active_pos["direction"] == "LONG"

            exit_reason = None
            exit_price = None

            if is_long:
                if not active_pos["t1_booked"]:
                    if high_price >= (entry + (t1 - entry) * 0.75) and sl < (entry + (t1 - entry) * 0.35):
                        active_pos["stop_loss"] = round(entry + (t1 - entry) * 0.35, 2)
                        active_pos["trailing_status"] = "PROFIT_LOCKED_35PCT"
                    elif high_price >= (entry + (t1 - entry) * 0.45) and sl < entry:
                        active_pos["stop_loss"] = entry
                        active_pos["trailing_status"] = "RISK_FREE_BREAKEVEN"

                if high_price >= t1 and not active_pos["t1_booked"]:
                    if shares > 1:
                        booked_shares = shares // 2
                        active_pos["shares"] -= booked_shares
                        active_pos["t1_booked"] = True
                        active_pos["stop_loss"] = entry
                        active_pos["trailing_status"] = "T1_BOOKED_RUNNER_ACTIVE"

                        pnl = round((t1 - entry) * booked_shares - 20.0, 2)
                        capital += pnl
                        trade_log.append({
                            "trade_id": f"BT-{len(trade_log)+1}-T1",
                            "symbol": sym,
                            "direction": "LONG",
                            "shares": booked_shares,
                            "entry_price": entry,
                            "exit_price": t1,
                            "entry_time": active_pos["entry_time"],
                            "exit_time": bar_time,
                            "exit_reason": "T1_PARTIAL_PROFIT_BOOKED",
                            "net_pnl": pnl,
                            "is_win": pnl > 0
                        })
                    else:
                        exit_reason = "TARGET_1_HIT"
                        exit_price = t1

                if active_pos["t1_booked"]:
                    runner_half_t2 = t1 + (t2 - t1) * 0.50
                    if high_price >= runner_half_t2 and active_pos["stop_loss"] < t1:
                        active_pos["stop_loss"] = t1
                        active_pos["trailing_status"] = "RUNNER_PROFIT_LOCKED_T1"

                    if high_price >= t2:
                        exit_reason = "TARGET_2_HIT"
                        exit_price = t2
                    elif low_price <= active_pos["stop_loss"]:
                        exit_reason = "RUNNER_BREAKEVEN_EXIT" if active_pos["stop_loss"] <= entry else "PROFIT_LOCKED_35PCT"
                        exit_price = active_pos["stop_loss"]
                elif low_price <= active_pos["stop_loss"]:
                    exit_reason = "STOP_LOSS_HIT"
                    exit_price = active_pos["stop_loss"]

            if exit_reason and exit_price:
                rem_shares = active_pos["shares"]
                gross = (exit_price - entry) * rem_shares if is_long else (entry - exit_price) * rem_shares
                net_pnl = round(gross - 25.0, 2)
                capital += net_pnl

                trade_log.append({
                    "trade_id": f"BT-{len(trade_log)+1}",
                    "symbol": sym,
                    "direction": active_pos["direction"],
                    "shares": rem_shares,
                    "entry_price": entry,
                    "exit_price": round(exit_price, 2),
                    "entry_time": active_pos["entry_time"],
                    "exit_time": bar_time,
                    "exit_reason": exit_reason,
                    "net_pnl": net_pnl,
                    "is_win": net_pnl > 0
                })
                active_pos = None

        if active_pos is None:
            supertrend = bar.get("supertrend", 0)
            ema9 = bar.get("ema9", 0)
            ema21 = bar.get("ema21", 0)
            rsi = bar.get("rsi", 50)
            atr = bar.get("atr", curr_price * 0.01)
            atr_val = atr if (atr and not math.isnan(atr)) else curr_price * 0.01

            is_bull_breakout = (
                curr_price > ema9 > ema21
                and (supertrend == 0 or curr_price > supertrend)
                and 52 <= rsi <= 74
                and curr_price > float(bar.get("open", curr_price))
            )

            if is_bull_breakout:
                entry = curr_price
                sl = round(entry - sl_mult * atr_val, 2)
                t1 = round(entry + t1_mult * atr_val, 2)
                t2 = round(entry + t2_mult * atr_val, 2)

                leverage = 5.0 if timeframe == "5m" else 1.0
                shares = max(2, min(500, int((budget * leverage) / entry)))

                active_pos = {
                    "direction": "LONG",
                    "entry_price": entry,
                    "target_1": t1,
                    "target_2": t2,
                    "stop_loss": sl,
                    "shares": shares,
                    "t1_booked": False,
                    "trailing_status": "NONE",
                    "entry_time": bar_time
                }

        peak_equity = max(peak_equity, capital)
        dd = peak_equity - capital
        dd_pct = (dd / peak_equity * 100.0) if peak_equity > 0 else 0.0
        max_drawdown_rupees = max(max_drawdown_rupees, dd)
        max_drawdown_pct = max(max_drawdown_pct, dd_pct)

        if record_equity:
            equity_curve.append({
                "time": bar_time,
                "equity": round(capital, 2),
                "drawdown_pct": round(dd_pct, 2)
            })

    if active_pos is not None:
        final_price = float(bars[-1].get("close", active_pos["entry_price"]))
        pnl = round((final_price - active_pos["entry_price"]) * active_pos["shares"] - 25.0, 2)
        capital += pnl
        trade_log.append({
            "trade_id": f"BT-{len(trade_log)+1}-FINAL",
            "symbol": sym,
            "direction": active_pos["direction"],
            "shares": active_pos["shares"],
            "entry_price": active_pos["entry_price"],
            "exit_price": final_price,
            "entry_time": active_pos["entry_time"],
            "exit_time": str(bars[-1].get("timestamp", "")),
            "exit_reason": "SIMULATION_END_CLOSE",
            "net_pnl": pnl,
            "is_win": pnl > 0
        })

    total_sim_trades = len(trade_log)
    winning_trades = [t for t in trade_log if t["is_win"]]
    losing_trades = [t for t in trade_log if not t["is_win"]]
    win_rate = round((len(winning_trades) / max(1, total_sim_trades)) * 100.0, 1) if total_sim_trades > 0 else 0.0
    gross_profit = round(sum(t["net_pnl"] for t in winning_trades), 2)
    gross_loss = round(abs(sum(t["net_pnl"] for t in losing_trades)), 2)
    net_pnl = round(capital - initial_capital, 2)
    net_roi_pct = round((net_pnl / initial_capital) * 100.0, 2)
    profit_factor = round(gross_profit / max(0.01, gross_loss), 2) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

    return {
        "final_capital": round(capital, 2),
        "net_pnl": net_pnl,
        "net_roi_pct": net_roi_pct,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_sim_trades,
        "winning_trades_count": len(winning_trades),
        "losing_trades_count": len(losing_trades),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "max_drawdown_inr": round(max_drawdown_rupees, 2),
        "equity_curve": equity_curve,
        "trade_log": trade_log
    }


@router.post("/run")
def run_backtest_simulation(req: BacktestRequest) -> Dict[str, Any]:
    """
    Executes a high-precision bar-by-bar historical backtest simulation of the
    AI Ensemble trading strategy on historical candle data.
    """
    sym = req.symbol.upper()
    provider = market_state.active_provider

    # 1. Fetch historical candle bars
    limit = max(100, min(800, req.days * (75 if req.timeframe == "5m" else 1)))
    candles_df = provider.get_candles(sym, timeframe=req.timeframe, count=limit)
    if candles_df is None or candles_df.empty or len(candles_df) < 25:
        available_count = len(candles_df) if candles_df is not None else 0
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical candle data for #{sym} ({available_count} bars available, minimum 25 required)."
        )

    import pandas as pd
    df = candles_df.copy()
    if "timestamp" not in df.columns:
        df = df.reset_index()
        if "index" in df.columns and "timestamp" not in df.columns:
            df.rename(columns={"index": "timestamp"}, inplace=True)
    df = enrich_candles_with_indicators(df)
    bars = df.to_dict(orient="records")

    res = _run_simulation_bars(
        bars=bars,
        sym=sym,
        initial_capital=req.initial_capital,
        budget=req.budget_per_trade,
        timeframe=req.timeframe,
        sl_mult=req.sl_multiplier or 1.4,
        t1_mult=req.target_multiplier or 1.8,
        t2_mult=req.runner_multiplier or 3.2,
        record_equity=True
    )

    eq_curve = res["equity_curve"]

    return {
        "success": True,
        "symbol": sym,
        "company_name": NSE_UNIVERSE.get(sym, {}).get("name", sym),
        "sector": NSE_UNIVERSE.get(sym, {}).get("sector", "NSE Equity"),
        "timeframe": req.timeframe,
        "days_simulated": req.days,
        "bars_analyzed": len(bars),
        "initial_capital": req.initial_capital,
        "final_capital": res["final_capital"],
        "net_pnl": res["net_pnl"],
        "net_roi_pct": res["net_roi_pct"],
        "win_rate": res["win_rate"],
        "profit_factor": res["profit_factor"],
        "total_trades": res["total_trades"],
        "winning_trades_count": res["winning_trades_count"],
        "losing_trades_count": res["losing_trades_count"],
        "max_drawdown_pct": res["max_drawdown_pct"],
        "max_drawdown_inr": res["max_drawdown_inr"],
        "equity_curve": eq_curve[::max(1, len(eq_curve) // 60)],
        "trade_log": res["trade_log"][::-1]
    }


@router.post("/optimize")
def optimize_strategy_parameters(req: OptimizeRequest) -> Dict[str, Any]:
    """
    Evaluates a quantitative parameter matrix (Target multiples, Stop multiples, Runner ratios)
    across historical bars to find the optimal mathematical setup configuration for this specific stock.
    """
    sym = req.symbol.upper()
    provider = market_state.active_provider
    limit = max(100, min(800, req.days * (75 if req.timeframe == "5m" else 1)))
    candles_df = provider.get_candles(sym, timeframe=req.timeframe, count=limit)
    if candles_df is None or candles_df.empty or len(candles_df) < 25:
        available_count = len(candles_df) if candles_df is not None else 0
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical candle data for #{sym} ({available_count} bars available, minimum 25 required)."
        )

    import pandas as pd
    df = candles_df.copy()
    if "timestamp" not in df.columns:
        df = df.reset_index()
        if "index" in df.columns and "timestamp" not in df.columns:
            df.rename(columns={"index": "timestamp"}, inplace=True)
    df = enrich_candles_with_indicators(df)
    bars = df.to_dict(orient="records")

    param_grid = [
        {"sl": 1.0, "t1": 1.5, "t2": 2.8, "name": "Aggressive Quick-Target (1.0x SL / 1.5x T1)"},
        {"sl": 1.2, "t1": 1.8, "t2": 3.2, "name": "Balanced Momentum (1.2x SL / 1.8x T1)"},
        {"sl": 1.4, "t1": 1.8, "t2": 3.2, "name": "Standard AI Ensemble (1.4x SL / 1.8x T1)"},
        {"sl": 1.5, "t1": 2.2, "t2": 3.8, "name": "Wide Swing Runner (1.5x SL / 2.2x T1)"},
        {"sl": 1.0, "t1": 2.0, "t2": 3.5, "name": "High R:R Asymmetric (1.0x SL / 2.0x T1)"},
        {"sl": 1.4, "t1": 2.4, "t2": 4.0, "name": "Deep Trend Expansion (1.4x SL / 2.4x T1)"},
    ]

    results = []
    for p in param_grid:
        metrics = _run_simulation_bars(
            bars=bars,
            sym=sym,
            initial_capital=req.initial_capital,
            budget=req.budget_per_trade,
            timeframe=req.timeframe,
            sl_mult=p["sl"],
            t1_mult=p["t1"],
            t2_mult=p["t2"],
            record_equity=False
        )
        score = round((metrics["win_rate"] * 0.4) + (min(metrics["profit_factor"], 4.0) * 15.0) + (metrics["net_roi_pct"] * 0.5), 1)
        results.append({
            "config_name": p["name"],
            "sl_mult": p["sl"],
            "t1_mult": p["t1"],
            "t2_mult": p["t2"],
            "sl_multiplier": p["sl"],
            "target_multiplier": p["t1"],
            "runner_multiplier": p["t2"],
            "win_rate": metrics["win_rate"],
            "profit_factor": metrics["profit_factor"],
            "net_pnl": metrics["net_pnl"],
            "net_roi_pct": metrics["net_roi_pct"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "total_trades": metrics["total_trades"],
            "optimization_score": score
        })

    results.sort(key=lambda x: x["optimization_score"], reverse=True)
    best = results[0] if results else None

    return {
        "success": True,
        "status": "success",
        "symbol": sym,
        "days_tested": req.days,
        "days": req.days,
        "timeframe": req.timeframe,
        "bars_analyzed": len(bars),
        "grid_tested": len(results),
        "optimal_config": best,
        "best_setup": best,
        "ranked_configurations": results,
        "optimization_matrix": results
    }
