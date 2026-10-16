"""
AI Auto-Trader API Router
Endpoints:
- GET /api/ai-trader/status: Current status, scheduler state, last scan summary
- POST /api/ai-trader/toggle: Enable/disable the 5-min auto trader
- POST /api/ai-trader/scan-now: Manually trigger an immediate 5-minute trade scan
- GET /api/ai-trader/history: Complete persistent log of transactions executed by AI
- GET /api/ai-trader/accuracy: Real-time accuracy analytics (win rate, profit factor, target hit vs SL hit ratio)
- POST /api/ai-trader/train-from-trades: Trigger model retraining enriched with AI paper transaction data
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
import datetime

from app.database import SessionLocal
from app.models.all_models import AITradeTransactionRecord
from app.services.ai_auto_trader import ai_auto_trader

router = APIRouter(prefix="/ai-trader", tags=["AI Automated Trader"])


class ToggleTraderRequest(BaseModel):
    enabled: bool
    enable_intraday: Optional[bool] = None
    enable_delivery: Optional[bool] = None
    budget_per_trade: Optional[float] = None
    delivery_budget: Optional[float] = None
    min_win_rate: Optional[float] = None
    min_conviction: Optional[float] = None


class AddDeliveryTradeRequest(BaseModel):
    symbol: str
    entry_price: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    stop_loss: Optional[float] = None
    shares: Optional[int] = None
    budget: Optional[float] = None


@router.get("/status")
def get_ai_trader_status() -> Dict[str, Any]:
    """Returns the operational status, current settings, and last scan metrics of the AI auto-trader."""
    # Ensure closed trades are synced
    ai_auto_trader.sync_closed_positions()

    db = SessionLocal()
    try:
        total_ai_trades = db.query(AITradeTransactionRecord).count()
        open_ai_trades = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.status == "OPEN").count()
        closed_ai_trades = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.status != "OPEN").count()
        winning_trades = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.is_win == True).count()

        intraday_count = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.trade_type == "INTRADAY").count()
        delivery_count = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.trade_type == "DELIVERY").count()

        win_rate = round((winning_trades / closed_ai_trades * 100.0), 1) if closed_ai_trades > 0 else 0.0

        from app.services.auto_trainer import auto_model_trainer
        return {
            "enabled": ai_auto_trader.enabled,
            "enable_intraday": getattr(ai_auto_trader, 'enable_intraday', True),
            "enable_delivery": getattr(ai_auto_trader, 'enable_delivery', True),
            "is_training": auto_model_trainer.is_training,
            "daily_training": auto_model_trainer.get_schedule_info(),
            "interval_minutes": ai_auto_trader.interval_seconds // 60,
            "min_win_rate_threshold_pct": round(ai_auto_trader.min_win_rate * 100, 1),
            "trade_budget_per_order": ai_auto_trader.trade_budget_per_order,
            "delivery_budget_per_order": ai_auto_trader.delivery_budget_per_order,
            "max_concurrent_ai_trades": ai_auto_trader.max_concurrent_ai_trades,
            "is_market_hours": ai_auto_trader.is_market_hours(),
            "last_run_time": ai_auto_trader.last_run_time.isoformat() + "Z" if ai_auto_trader.last_run_time else None,
            "last_scan_result": ai_auto_trader.last_scan_result,
            "statistics": {
                "total_trades": total_ai_trades,
                "intraday_trades": intraday_count,
                "delivery_trades": delivery_count,
                "open_trades": open_ai_trades,
                "closed_trades": closed_ai_trades,
                "winning_trades": winning_trades,
                "win_rate": win_rate
            }
        }
    finally:
        db.close()


@router.post("/toggle")
def toggle_ai_trader(req: ToggleTraderRequest) -> Dict[str, Any]:
    """Enables or disables the AI automated trading daemon, or configures intraday/delivery modes."""
    ai_auto_trader.enabled = req.enabled
    if req.enable_intraday is not None:
        ai_auto_trader.enable_intraday = req.enable_intraday
    if req.enable_delivery is not None:
        ai_auto_trader.enable_delivery = req.enable_delivery
    if req.budget_per_trade and req.budget_per_trade > 0:
        ai_auto_trader.trade_budget_per_order = req.budget_per_trade
    if req.delivery_budget and req.delivery_budget > 0:
        ai_auto_trader.delivery_budget_per_order = req.delivery_budget
    if req.min_win_rate and 0 < req.min_win_rate <= 1.0:
        ai_auto_trader.min_win_rate = req.min_win_rate
    if req.min_conviction and 0 < req.min_conviction <= 1.0:
        ai_auto_trader.min_conviction = req.min_conviction

    status_str = "ENABLED" if ai_auto_trader.enabled else "PAUSED"
    modes = []
    if ai_auto_trader.enable_intraday:
        modes.append("Intraday (MIS)")
    if ai_auto_trader.enable_delivery:
        modes.append("Delivery (CNC)")
    mode_str = " + ".join(modes) if modes else "None"

    return {
        "success": True,
        "enabled": ai_auto_trader.enabled,
        "enable_intraday": ai_auto_trader.enable_intraday,
        "enable_delivery": ai_auto_trader.enable_delivery,
        "trade_budget_per_order": ai_auto_trader.trade_budget_per_order,
        "delivery_budget_per_order": ai_auto_trader.delivery_budget_per_order,
        "message": f"AI Auto-Trader is now {status_str} [Modes: {mode_str}]."
    }


@router.post("/add-delivery-trade")
def add_delivery_trade_to_ai_trader(req: AddDeliveryTradeRequest) -> Dict[str, Any]:
    """
    Manually injects any delivery stock into the AI Auto-Trader.
    Calculates entry, optimal targets, and stop loss, places paper trade, and
    activates continuous 3-second live monitoring with Breakeven Trailing Stop and Target 1 exit.
    """
    try:
        res = ai_auto_trader.add_custom_delivery_trade(
            symbol=req.symbol,
            entry_price=req.entry_price,
            target_1=req.target_1,
            target_2=req.target_2,
            stop_loss=req.stop_loss,
            shares=req.shares,
            budget=req.budget
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to auto-add delivery trade: {ex}")


@router.post("/scan-now")
def run_scan_now() -> Dict[str, Any]:
    """Forces an immediate 5-minute cycle scan for both Intraday and Delivery setups."""
    res = ai_auto_trader.scan_and_execute_trades()
    return {
        "success": True,
        "scan_result": res
    }


@router.get("/history")
def get_ai_trades_history(limit: int = 100) -> Dict[str, Any]:
    """
    Returns the complete persistent audit history of all trades executed by the AI.
    Includes exact entry/exit timestamps, entry price, targets, stop-loss, realized P&L,
    ML probability at entry, and exit reason.
    """
    ai_auto_trader.sync_closed_positions()

    db = SessionLocal()
    try:
        records = db.query(AITradeTransactionRecord).order_by(AITradeTransactionRecord.entry_time.desc()).limit(limit).all()
        history = []
        for r in records:
            history.append({
                "trade_id": r.trade_id,
                "position_id": r.position_id,
                "symbol": r.symbol,
                "direction": r.direction,
                "trade_type": r.trade_type,
                "strategy": r.strategy,
                "entry_time": r.entry_time.isoformat() + "Z" if r.entry_time else None,
                "exit_time": r.exit_time.isoformat() + "Z" if r.exit_time else None,
                "entry_price": r.entry_price,
                "target_price": r.target_price,
                "stop_loss_price": r.stop_loss_price,
                "exit_price": r.exit_price,
                "quantity": r.quantity,
                "gross_pnl": r.gross_pnl,
                "net_pnl": r.net_pnl,
                "pnl_pct": r.pnl_pct,
                "total_charges": r.total_charges,
                "status": r.status,
                "is_win": r.is_win,
                "exit_reason": r.exit_reason,
                "ml_probability": r.ml_probability,
                "conviction_score": r.conviction_score,
                "risk_reward_ratio": r.risk_reward_ratio,
                "market_regime": r.market_regime,
                "trained_in_ml": r.trained_in_ml
            })

        closed = [h for h in history if h["status"] != "OPEN"]
        wins = [h for h in closed if h["is_win"]]
        win_rate = round((len(wins) / len(closed) * 100.0), 1) if closed else 0.0

        return {
            "total_count": len(history),
            "open_count": len([h for h in history if h["status"] == "OPEN"]),
            "closed_count": len(closed),
            "win_rate": win_rate,
            "history": history
        }
    finally:
        db.close()


@router.get("/accuracy")
def get_ai_trades_accuracy() -> Dict[str, Any]:
    """
    Returns detailed accuracy and statistical metrics of the AI's automated trades.
    Allows measuring true precision: Target Hit vs Stop Hit, Average R-multiple, Win Rate, and Total P&L.
    """
    ai_auto_trader.sync_closed_positions()

    db = SessionLocal()
    try:
        records = db.query(AITradeTransactionRecord).all()
        total_count = len(records)
        closed_records = [r for r in records if r.status != "OPEN"]
        closed_count = len(closed_records)

        target_hits = [r for r in closed_records if r.status == "PROFIT_BOOKED" or (r.exit_reason and "TARGET" in r.exit_reason.upper())]
        sl_hits = [r for r in closed_records if r.status == "STOP_LOSS_HIT" or (r.exit_reason and "STOP" in r.exit_reason.upper())]
        wins = [r for r in closed_records if r.net_pnl > 0]
        losses = [r for r in closed_records if r.net_pnl <= 0]

        total_profit = sum(r.net_pnl for r in wins)
        total_loss = abs(sum(r.net_pnl for r in losses))
        net_realized_pnl = round(total_profit - total_loss, 2)

        win_rate = round((len(wins) / closed_count * 100.0), 1) if closed_count > 0 else 0.0
        profit_factor = round(total_profit / max(total_loss, 0.01), 2) if total_loss > 0 else (round(total_profit, 2) if total_profit > 0 else 1.0)

        # Intraday vs Delivery breakdown
        intra_closed = [r for r in closed_records if r.trade_type == "INTRADAY"]
        deliv_closed = [r for r in closed_records if r.trade_type == "DELIVERY"]
        intra_wins = [r for r in intra_closed if r.net_pnl > 0]
        deliv_wins = [r for r in deliv_closed if r.net_pnl > 0]

        intra_win_rate = round(len(intra_wins) / len(intra_closed) * 100.0, 1) if intra_closed else 0.0
        deliv_win_rate = round(len(deliv_wins) / len(deliv_closed) * 100.0, 1) if deliv_closed else 0.0

        return {
            "total_trades": total_count,
            "closed_trades": closed_count,
            "open_trades": total_count - closed_count,
            "win_rate": win_rate,
            "target_hit_count": len(target_hits),
            "stop_loss_hit_count": len(sl_hits),
            "profit_factor": profit_factor,
            "total_net_pnl": net_realized_pnl,
            "gross_profit": round(total_profit, 2),
            "gross_loss": round(total_loss, 2),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "intraday_closed_count": len(intra_closed),
            "delivery_closed_count": len(deliv_closed),
            "intraday_win_rate": intra_win_rate,
            "delivery_win_rate": deliv_win_rate,
            "accuracy_rating": "EXCELLENT" if win_rate >= 60 else ("GOOD" if win_rate >= 50 else "OPTIMIZING")
        }
    finally:
        db.close()


@router.post("/train-daily")
def trigger_daily_training(force: bool = False) -> Dict[str, Any]:
    """
    Triggers automated post-market dual-model retraining (Intraday + Delivery) immediately.
    Syncs fresh market candles, trains both ensembles, incorporates closed trades,
    and hot-swaps models in memory with zero downtime.
    """
    from app.services.auto_trainer import auto_model_trainer
    return auto_model_trainer.run_auto_train_job(force=force, is_daily=True)


@router.post("/train-from-trades")
def trigger_train_from_ai_trades() -> Dict[str, Any]:
    """
    Exports closed AI paper trade transactions as custom labelled samples and
    triggers model retraining to fine-tune future predictions.
    """
    from app.services.auto_trainer import auto_model_trainer
    db = SessionLocal()
    try:
        closed_trades = db.query(AITradeTransactionRecord).filter(
            AITradeTransactionRecord.status != "OPEN",
            AITradeTransactionRecord.exit_price != None
        ).all()

        sample_count = len(closed_trades)
        if sample_count < 1:
            return {
                "success": False,
                "message": "Requires at least 1 completed AI trade to retrain. Place or wait for an AI trade to complete first."
            }

        # Mark trades as incorporated
        for t in closed_trades:
            t.trained_in_ml = True
        db.commit()

        # Trigger background auto trainer for both models
        train_res = auto_model_trainer.run_auto_train_job(force=True, is_daily=False)

        if not train_res.get("started", False):
            return {
                "success": False,
                "message": train_res.get("message", "Model retraining is already currently in progress."),
                "incorporated_samples": sample_count
            }

        return {
            "success": True,
            "message": f"Successfully incorporated {sample_count} AI trade transaction{'s' if sample_count > 1 else ''} into ML training pipeline. Retraining started in background.",
            "incorporated_samples": sample_count
        }
    finally:
        db.close()

