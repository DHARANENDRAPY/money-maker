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
    budget_per_trade: Optional[float] = None
    min_win_rate: Optional[float] = None


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

        win_rate = round((winning_trades / closed_ai_trades * 100.0), 1) if closed_ai_trades > 0 else 0.0

        return {
            "enabled": ai_auto_trader.enabled,
            "interval_minutes": ai_auto_trader.interval_seconds // 60,
            "min_win_rate_threshold_pct": round(ai_auto_trader.min_win_rate * 100, 1),
            "trade_budget_per_order": ai_auto_trader.trade_budget_per_order,
            "max_concurrent_ai_trades": ai_auto_trader.max_concurrent_ai_trades,
            "is_market_hours": ai_auto_trader.is_market_hours(),
            "last_run_time": ai_auto_trader.last_run_time.isoformat() + "Z" if ai_auto_trader.last_run_time else None,
            "last_scan_result": ai_auto_trader.last_scan_result,
            "statistics": {
                "total_trades": total_ai_trades,
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
    """Enables or disables the AI 5-minute automated trading daemon."""
    ai_auto_trader.enabled = req.enabled
    if req.budget_per_trade and req.budget_per_trade > 0:
        ai_auto_trader.trade_budget_per_order = req.budget_per_trade
    if req.min_win_rate and 0 < req.min_win_rate <= 1.0:
        ai_auto_trader.min_win_rate = req.min_win_rate

    return {
        "success": True,
        "enabled": ai_auto_trader.enabled,
        "message": f"AI Auto-Trader is now {'ENABLED (Running every 5 min)' if ai_auto_trader.enabled else 'PAUSED'}."
    }


@router.post("/scan-now")
def run_scan_now() -> Dict[str, Any]:
    """Forces an immediate 5-minute cycle scan and executes qualified paper trades."""
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

        # Average winning and losing trades
        avg_win = round(total_profit / len(wins), 2) if wins else 0.0
        avg_loss = round(total_loss / len(losses), 2) if losses else 0.0

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
            "accuracy_rating": "EXCELLENT" if win_rate >= 60 else ("GOOD" if win_rate >= 50 else "OPTIMIZING")
        }
    finally:
        db.close()


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
        if sample_count < 3:
            return {
                "success": False,
                "message": f"Requires at least 3 completed AI transactions to retrain (currently {sample_count}). AI will auto-train as trades execute."
            }

        # Mark trades as incorporated
        for t in closed_trades:
            t.trained_in_ml = True
        db.commit()

        # Trigger background auto trainer
        auto_model_trainer.run_auto_train_job()

        return {
            "success": True,
            "message": f"Successfully incorporated {sample_count} AI trade transactions into training pipeline.",
            "incorporated_samples": sample_count
        }
    finally:
        db.close()
