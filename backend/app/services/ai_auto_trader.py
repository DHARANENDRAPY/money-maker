"""
AI Automated Intraday Trader Service
- Evaluates market every 5 minutes during live market hours
- Filters strictly for INTRADAY setups where:
    * ML Probability > 50% (Win Rate > 50%)
    * Trade Type == 'INTRADAY' (NEVER DELIVERY)
- Automatically pushes high-probability setups into Paper Trading
- Auto Stop Loss attached to every trade
- Automated Profit Booking: Exits when Target 1 / Target 2 is achieved or User manually books profit
- Maintains a dedicated persistent SQLite database table (`ai_trade_transactions`)
  recording all AI trade transactions with complete feature metrics for future ML model retraining and accuracy tracking.
"""
import asyncio
import logging
import datetime
import uuid
from typing import Dict, List, Any, Optional

from app.database import SessionLocal
from app.models.all_models import AITradeTransactionRecord
from app.services.market_state import market_state
from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade

logger = logging.getLogger("ai_auto_trader")


class AIAutoTraderService:
    def __init__(self):
        self.enabled: bool = True
        self.min_win_rate: float = 0.52  # Must have positive statistical edge (>= 52% calibrated ML prob)
        self.min_conviction: float = 0.80  # Strict gate: AI must be >= 80% confident (High Conviction)
        self.trade_budget_per_order: float = 2000.0  # ₹2,000 INR per paper trade
        self.interval_seconds: int = 300  # 5 minutes
        self.max_concurrent_ai_trades: int = 5
        self.last_run_time: Optional[datetime.datetime] = None
        self.last_scan_result: Dict[str, Any] = {
            "status": "IDLE",
            "evaluated_count": 0,
            "qualified_count": 0,
            "placed_trades": [],
            "message": "AI Auto-Trader initialized."
        }

    def is_market_hours(self) -> bool:
        """
        NSE trading hours: Mon-Fri, 09:15 to 15:15 IST (Auto stops at 15:15 for MIS square-off).
        Strictly requires live authenticated broker connection.
        """
        if not market_state.active_provider.is_live_feed():
            return False

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)
        weekday = now_ist.weekday()

        if weekday >= 5:
            return False
        total_minutes = now_ist.hour * 60 + now_ist.minute
        return (9 * 60 + 15 <= total_minutes <= 15 * 60 + 15)

    def scan_and_execute_trades(self) -> Dict[str, Any]:
        """
        Executes a 5-minute cycle:
        1. Queries AI recommendations (strictly Intraday)
        2. Filters only trades where AI Conviction >= 80% (>= 0.80) and ML prob >= 52%
        3. Excludes existing open positions in the same symbol
        4. Enforces safety limits (max concurrent trades, cash balance)
        5. Executes paper trade and logs to `ai_trade_transactions` table for future ML training
        """
        if not self.enabled:
            return {"status": "DISABLED", "message": "AI Auto-Trader is disabled by user."}

        from app.routers.recommendations import get_ai_recommendations

        self.last_run_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info("🤖 AI 5-Min Auto-Trader scanning for high-conviction Intraday trades (>=80% AI confidence)...")

        # 1. Fetch fresh recommendations (Intraday scanner)
        rec_data = get_ai_recommendations(limit=10)
        top_recs = rec_data.get("top_recommendations", [])

        current_open_positions = portfolio.positions
        open_symbols = {p["symbol"].upper() for p in current_open_positions.values()}

        evaluated_count = len(top_recs)
        qualified_candidates = []

        for rec in top_recs:
            sym = rec.get("symbol", "").upper()
            ml_prob = rec.get("ml_probability", 0.0)
            conviction = rec.get("conviction_score", 0.0)
            entry = rec.get("entry_price", 0.0)
            target = rec.get("target_price", 0.0)
            sl = rec.get("stop_loss", 0.0)
            direction = rec.get("direction", "LONG").upper()
            target_pct = abs(target - entry) / entry if entry > 0 else 0.0

            # Strict Checks:
            # - Strictly Intraday (NO DELIVERY)
            # - High AI Conviction (>= 80% confidence)
            # - Calibrated ML edge (>= 52% win rate)
            # - Valid prices with direction alignment:
            #   LONG: sl < entry < target; SHORT: sl > entry > target
            # - Realistic intraday target distance (<= 2.5%)
            # - Not already an open position in this stock
            direction_valid = (sl < entry < target) if direction == "LONG" else (sl > entry > target)
            if (conviction >= self.min_conviction and ml_prob >= self.min_win_rate
                    and entry > 0 and target > 0 and sl > 0
                    and direction_valid and target_pct <= 0.025):
                if sym not in open_symbols:
                    qualified_candidates.append(rec)

        placed_trades = []
        db = SessionLocal()

        try:
            for cand in qualified_candidates:
                # Limit concurrent AI open trades
                if len(portfolio.positions) >= self.max_concurrent_ai_trades:
                    logger.info(f"Reached max concurrent AI trades limit ({self.max_concurrent_ai_trades}). Skipping remaining.")
                    break

                sym = cand["symbol"]
                direction = cand.get("direction", "LONG").upper()
                entry = cand.get("entry_price", 0.0)
                target = cand.get("target_price", 0.0)
                sl = cand.get("stop_loss", 0.0)
                ml_prob = cand.get("ml_probability", 0.0)
                conviction = cand.get("conviction_score", 0.0)
                strategy = cand.get("strategy", "AI High-WinRate Intraday")
                rr = cand.get("risk_reward_ratio", 1.5)
                rvol = cand.get("rvol", 1.0)
                market_regime = cand.get("market_regime", "UNCERTAIN")
                supporting = cand.get("supporting_factors", [])

                # Calculate share quantity based on budget and 5x intraday margin
                buying_power = self.trade_budget_per_order * 5.0
                qty = max(1, int(buying_power / entry))

                # Prepare Paper Trade Request
                req = PlacePaperTradeRequest(
                    symbol=sym,
                    direction=direction,
                    trade_type="INTRADAY",
                    product_type="MIS",
                    entry_price=entry,
                    target_1=target,
                    stop_loss=sl,
                    budget=self.trade_budget_per_order,
                    shares=qty,
                    strategy=f"AI Bot: {strategy}",
                    source="AI_AUTO_TRADER"
                )

                try:
                    order_res = place_paper_trade(req)
                    pos_info = order_res.get("position", {})
                    pos_id = pos_info.get("position_id")

                    # Log to dedicated AI Trade Transaction table for future AI model training
                    trade_uuid = f"AITRADE-{uuid.uuid4().hex[:10].upper()}"
                    tx_record = AITradeTransactionRecord(
                        trade_id=trade_uuid,
                        position_id=str(pos_id),
                        symbol=sym,
                        direction=direction,
                        trade_type="INTRADAY",
                        entry_time=datetime.datetime.now(datetime.timezone.utc),
                        entry_price=entry,
                        target_price=target,
                        stop_loss_price=sl,
                        quantity=qty,
                        status="OPEN",
                        strategy=strategy,
                        ml_probability=ml_prob,
                        conviction_score=conviction,
                        risk_reward_ratio=rr,
                        rvol=rvol,
                        market_regime=market_regime,
                        supporting_factors=supporting,
                        trained_in_ml=False
                    )
                    db.add(tx_record)
                    db.commit()

                    placed_trades.append({
                        "trade_id": trade_uuid,
                        "position_id": pos_id,
                        "symbol": sym,
                        "direction": direction,
                        "entry_price": entry,
                        "target_price": target,
                        "stop_loss": sl,
                        "shares": qty,
                        "ml_probability_pct": round(ml_prob * 100, 1),
                        "conviction_score": conviction,
                        "placed_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
                    })
                    logger.info(f"✅ AI Auto-Trader opened paper trade: {qty} shares of {sym} ({direction}) @ ₹{entry:,.2f} | Win Rate: {ml_prob*100:.1f}% | SL: ₹{sl} | TGT: ₹{target}")

                    # Update open_symbols to prevent duplicate entries in same cycle
                    open_symbols.add(sym.upper())

                except Exception as ex:
                    logger.error(f"Failed to place auto-trade for {sym}: {ex}")

        finally:
            db.close()

        result_summary = {
            "status": "SUCCESS",
            "last_run": self.last_run_time.isoformat() + "Z",
            "evaluated_count": evaluated_count,
            "qualified_count": len(qualified_candidates),
            "placed_count": len(placed_trades),
            "placed_trades": placed_trades,
            "message": f"Evaluated {evaluated_count} stocks; placed {len(placed_trades)} high-probability trades (>50% win rate)."
        }
        self.last_scan_result = result_summary
        return result_summary

    def sync_closed_positions(self):
        """
        Synchronizes newly closed positions from Paper Trading into `ai_trade_transactions`.
        Ensures exact exit prices, net P&L, win/loss status, and exit reasons are recorded for ML training.
        """
        db = SessionLocal()
        try:
            # Find open AI transactions in DB
            open_txs = db.query(AITradeTransactionRecord).filter(AITradeTransactionRecord.status == "OPEN").all()
            if not open_txs:
                return

            closed_map = {str(t["position_id"]): t for t in portfolio.closed_trades}

            for tx in open_txs:
                if tx.position_id in closed_map:
                    closed_info = closed_map[tx.position_id]
                    exit_price = closed_info.get("exit_price")
                    exit_reason = closed_info.get("exit_reason", "MANUAL_EXIT")
                    net_pnl = closed_info.get("realized_pnl", 0.0)
                    gross_pnl = closed_info.get("gross_pnl", 0.0)
                    pnl_pct = closed_info.get("realized_pnl_pct", 0.0)
                    charges = closed_info.get("charges", 0.0)
                    is_win = (net_pnl > 0)

                    tx.exit_time = datetime.datetime.now(datetime.timezone.utc)
                    tx.exit_price = exit_price
                    tx.gross_pnl = gross_pnl
                    tx.net_pnl = net_pnl
                    tx.pnl_pct = pnl_pct
                    tx.total_charges = charges
                    tx.is_win = is_win
                    tx.exit_reason = exit_reason

                    if "TARGET" in exit_reason.upper():
                        tx.status = "PROFIT_BOOKED"
                    elif "STOP" in exit_reason.upper():
                        tx.status = "STOP_LOSS_HIT"
                    else:
                        tx.status = "CLOSED"

                    logger.info(f"🔄 Synced AI Trade exit: {tx.symbol} -> {tx.status} (Net P&L: ₹{net_pnl:,.2f})")

            db.commit()
        except Exception as e:
            logger.error(f"Error syncing closed AI trades: {e}")
        finally:
            db.close()


ai_auto_trader = AIAutoTraderService()


async def ai_auto_trader_loop():
    """
    Background asyncio daemon:
    Runs every 5 minutes (300s):
    1. Triggers portfolio quote update (checks Target 1 profit book & Stop Loss hit)
    2. Synchronizes closed AI trades into the dedicated database
    3. Runs AI intraday trade scanner for win rate > 50% setups and pushes qualified trades into paper trading
    """
    logger.info("Starting AI 5-Minute Auto-Trader daemon loop...")
    await asyncio.sleep(20)  # Initial grace period for engine warmup

    while True:
        try:
            # 1. Update live quotes and trigger auto Target/SL execution on open positions
            try:
                portfolio.get_summary()
                ai_auto_trader.sync_closed_positions()
            except Exception as e:
                logger.warning(f"Error in portfolio auto-exit check: {e}")

            # 2. Check market hours and execute 5-minute trade scan
            if ai_auto_trader.enabled and ai_auto_trader.is_market_hours():
                try:
                    ai_auto_trader.scan_and_execute_trades()
                except Exception as e:
                    logger.error(f"Error executing AI 5-min trade scan: {e}")

            # Sleep for exactly 5 minutes (300 seconds)
            await asyncio.sleep(ai_auto_trader.interval_seconds)

        except asyncio.CancelledError:
            logger.info("AI Auto-Trader loop cancelled.")
            break
        except Exception as err:
            logger.error(f"Unexpected error in ai_auto_trader_loop: {err}")
            await asyncio.sleep(60)
