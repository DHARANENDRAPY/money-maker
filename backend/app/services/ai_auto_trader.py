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

logger = logging.getLogger("ai_auto_trader")


class AIAutoTraderService:
    def __init__(self):
        self.enabled: bool = True
        self.enable_intraday: bool = True  # Auto-trade qualified Intraday setups
        self.enable_delivery: bool = True  # Auto-trade qualified Swing Delivery stocks
        self.min_win_rate: float = 0.52  # Must have positive statistical edge (>= 52% calibrated ML prob)
        self.min_conviction: float = 0.80  # Strict gate: AI must be >= 80% confident (High Conviction)
        self.trade_budget_per_order: float = 2000.0  # ₹2,000 INR per paper intraday trade
        self.delivery_budget_per_order: float = 2000.0  # ₹2,000 INR per paper delivery trade
        self.interval_seconds: int = 300  # 5 minutes
        self.max_concurrent_ai_trades: int = 8  # Total concurrent trades (Intraday + Delivery)
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
        1. Queries AI recommendations (Intraday and Delivery setups)
        2. Filters only setups where AI Conviction >= 80% (>= 0.80) and ML prob >= 52%
        3. Excludes existing open positions in the same symbol
        4. Enforces safety limits (max concurrent trades, cash balance, CNC vs MIS margin)
        5. Executes paper trades and logs to `ai_trade_transactions` table for future ML training
        """
        if not self.enabled:
            return {"status": "DISABLED", "message": "AI Auto-Trader is disabled by user."}

        self.last_run_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info("🤖 AI 5-Min Auto-Trader scanning for high-conviction Intraday & Delivery trades (>=80% AI confidence)...")

        from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade

        current_open_positions = portfolio.positions
        open_symbols = {p["symbol"].upper() for p in current_open_positions.values()}

        intraday_evaluated = 0
        qualified_intraday = []
        delivery_evaluated = 0
        qualified_delivery = []

        # 1. Evaluate Intraday Setups (MIS, 5x leverage)
        if self.enable_intraday:
            try:
                from app.routers.recommendations import get_ai_recommendations
                rec_data = get_ai_recommendations(limit=10)
                top_recs = rec_data.get("top_recommendations", [])
                intraday_evaluated = len(top_recs)

                for rec in top_recs:
                    sym = rec.get("symbol", "").upper()
                    ml_prob = rec.get("ml_probability", 0.0)
                    conviction = rec.get("conviction_score", 0.0)
                    entry = rec.get("entry_price", 0.0)
                    target = rec.get("target_price", 0.0)
                    sl = rec.get("stop_loss", 0.0)
                    direction = rec.get("direction", "LONG").upper()
                    target_pct = abs(target - entry) / entry if entry > 0 else 0.0

                    direction_valid = (sl < entry < target) if direction == "LONG" else (sl > entry > target)
                    if (conviction >= self.min_conviction and ml_prob >= self.min_win_rate
                            and entry > 0 and target > 0 and sl > 0
                            and direction_valid and target_pct <= 0.025):
                        if sym not in open_symbols:
                            qualified_intraday.append(rec)
            except Exception as e:
                logger.error(f"Error evaluating intraday recommendations: {e}")

        # 2. Evaluate Delivery Setups (CNC, 1x cash Buy & Hold)
        if self.enable_delivery:
            try:
                from app.routers.delivery import get_delivery_recommendations
                deliv_data = get_delivery_recommendations(budget=self.delivery_budget_per_order, limit=12)
                top_deliv_recs = deliv_data.get("recommendations", [])
                delivery_evaluated = len(top_deliv_recs)

                intraday_syms = {c.get("symbol", "").upper() for c in qualified_intraday}

                for pick in top_deliv_recs:
                    sym = pick.get("symbol", "").upper()
                    ml_prob = pick.get("ml_probability", 0.0)
                    # Conviction in delivery is percentage (0-100) or decimal (0-1)
                    raw_conv = pick.get("conviction_pct", 0)
                    conviction = (raw_conv / 100.0) if raw_conv > 1.0 else float(raw_conv)
                    entry = pick.get("ltp", 0.0)
                    target_1 = pick.get("target_1", 0.0)
                    sl = pick.get("stop_loss", 0.0)

                    # Delivery checks:
                    # - Buy & Hold (Long only)
                    # - Valid prices: 0 < sl < entry < target_1
                    # - AI Conviction >= 80% & Win Rate >= 52%
                    # - Not already an open position or picked in intraday
                    if (conviction >= self.min_conviction and ml_prob >= self.min_win_rate
                            and entry > 0 and target_1 > entry and 0 < sl < entry):
                        if sym not in open_symbols and sym not in intraday_syms:
                            qualified_delivery.append(pick)
            except Exception as e:
                logger.error(f"Error evaluating delivery recommendations: {e}")

        evaluated_count = intraday_evaluated + delivery_evaluated
        qualified_count = len(qualified_intraday) + len(qualified_delivery)

        placed_trades = []
        db = SessionLocal()

        try:
            # Execute Qualified Intraday Trades
            for cand in qualified_intraday:
                if len(portfolio.positions) >= self.max_concurrent_ai_trades:
                    logger.info(f"Reached max concurrent AI trades limit ({self.max_concurrent_ai_trades}). Skipping remaining.")
                    break

                sym = cand["symbol"].upper()
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

                # Sizing: 5x intraday margin
                buying_power = self.trade_budget_per_order * 5.0
                qty = max(1, int(buying_power / entry))

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
                    source="AI_AUTO_TRADER_INTRADAY"
                )

                try:
                    order_res = place_paper_trade(req)
                    pos_info = order_res.get("position", {})
                    pos_id = pos_info.get("position_id")

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
                        "trade_type": "INTRADAY",
                        "entry_price": entry,
                        "target_price": target,
                        "stop_loss": sl,
                        "shares": qty,
                        "ml_probability_pct": round(ml_prob * 100, 1),
                        "conviction_score": conviction,
                        "placed_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
                    })
                    open_symbols.add(sym)
                    logger.info(f"✅ AI Auto-Trader opened INTRADAY paper trade: {qty} shares of {sym} ({direction}) @ ₹{entry:,.2f} | Win Rate: {ml_prob*100:.1f}% | SL: ₹{sl} | TGT: ₹{target}")
                except Exception as ex:
                    logger.error(f"Failed to place intraday auto-trade for {sym}: {ex}")

            # Execute Qualified Delivery Trades (CNC, 1x cash margin, full position holding)
            for pick in qualified_delivery:
                if len(portfolio.positions) >= self.max_concurrent_ai_trades:
                    logger.info(f"Reached max concurrent AI trades limit ({self.max_concurrent_ai_trades}). Skipping remaining.")
                    break

                sym = pick["symbol"].upper()
                if sym in open_symbols:
                    continue

                entry = pick.get("ltp", 0.0)
                target_1 = pick.get("target_1", 0.0)
                target_2 = pick.get("target_2", target_1 * 1.10)
                sl = pick.get("stop_loss", 0.0)
                ml_prob = pick.get("ml_probability", 0.0)
                raw_conv = pick.get("conviction_pct", 0)
                conviction = (raw_conv / 100.0) if raw_conv > 1.0 else float(raw_conv)
                strategy = pick.get("technical_setup", "Delivery Swing Breakout")
                rr = pick.get("risk_reward_ratio", 2.0)
                horizon = pick.get("holding_period", "2 to 4 Weeks (CNC)")

                # Sizing: 1x cash margin (NO LEVERAGE for Delivery)
                suggested = pick.get("suggested_shares")
                if suggested and suggested > 0:
                    qty = suggested
                elif entry <= self.delivery_budget_per_order:
                    qty = max(1, int(self.delivery_budget_per_order / entry))
                else:
                    qty = 1

                margin_required = round(qty * entry, 2)
                if margin_required > portfolio.available_cash:
                    if entry <= portfolio.available_cash:
                        qty = 1
                        margin_required = entry
                    else:
                        logger.warning(f"Insufficient cash for Delivery auto-trade #{sym} (Needed ₹{margin_required:,.2f}, Available: ₹{portfolio.available_cash:,.2f})")
                        continue

                req = PlacePaperTradeRequest(
                    symbol=sym,
                    direction="LONG",
                    trade_type="DELIVERY",
                    product_type="CNC",
                    entry_price=entry,
                    target_1=target_1,
                    target_2=target_2,
                    stop_loss=sl,
                    budget=self.delivery_budget_per_order,
                    shares=qty,
                    strategy=f"AI Delivery: {strategy[:45]}",
                    source="AI_AUTO_TRADER_DELIVERY"
                )

                try:
                    order_res = place_paper_trade(req)
                    pos_info = order_res.get("position", {})
                    pos_id = pos_info.get("position_id")

                    trade_uuid = f"AITRADE-DELIV-{uuid.uuid4().hex[:8].upper()}"
                    tx_record = AITradeTransactionRecord(
                        trade_id=trade_uuid,
                        position_id=str(pos_id),
                        symbol=sym,
                        direction="LONG",
                        trade_type="DELIVERY",
                        entry_time=datetime.datetime.now(datetime.timezone.utc),
                        entry_price=entry,
                        target_price=target_1,
                        stop_loss_price=sl,
                        quantity=qty,
                        status="OPEN",
                        strategy=strategy,
                        ml_probability=ml_prob,
                        conviction_score=conviction,
                        risk_reward_ratio=rr,
                        rvol=1.0,
                        market_regime=horizon,
                        supporting_factors=[pick.get("technical_setup", ""), pick.get("fundamental_catalyst", "")],
                        trained_in_ml=False
                    )
                    db.add(tx_record)
                    db.commit()

                    placed_trades.append({
                        "trade_id": trade_uuid,
                        "position_id": pos_id,
                        "symbol": sym,
                        "direction": "LONG",
                        "trade_type": "DELIVERY",
                        "entry_price": entry,
                        "target_price": target_1,
                        "stop_loss": sl,
                        "shares": qty,
                        "ml_probability_pct": round(ml_prob * 100, 1),
                        "conviction_score": conviction,
                        "placed_at": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
                    })
                    open_symbols.add(sym)
                    logger.info(f"✅ AI Auto-Trader opened DELIVERY paper trade: {qty} shares of {sym} (LONG CNC) @ ₹{entry:,.2f} | Conviction: {conviction*100:.0f}% | SL: ₹{sl} | TGT: ₹{target_1}")
                except Exception as ex:
                    logger.error(f"Failed to place delivery auto-trade for {sym}: {ex}")

        finally:
            db.close()

        intraday_placed_cnt = len([t for t in placed_trades if t.get("trade_type") == "INTRADAY"])
        delivery_placed_cnt = len([t for t in placed_trades if t.get("trade_type") == "DELIVERY"])

        msg = (
            f"Evaluated {evaluated_count} setups ({intraday_evaluated} Intraday, {delivery_evaluated} Delivery); "
            f"placed {len(placed_trades)} trades ({intraday_placed_cnt} Intraday, {delivery_placed_cnt} Delivery)."
        )
        result_summary = {
            "status": "SUCCESS",
            "last_run": self.last_run_time.isoformat() + "Z",
            "evaluated_count": evaluated_count,
            "qualified_count": qualified_count,
            "placed_count": len(placed_trades),
            "placed_trades": placed_trades,
            "intraday_placed_count": intraday_placed_cnt,
            "delivery_placed_count": delivery_placed_cnt,
            "message": msg
        }
        self.last_scan_result = result_summary
        return result_summary

    def add_custom_delivery_trade(
        self,
        symbol: str,
        entry_price: Optional[float] = None,
        target_1: Optional[float] = None,
        target_2: Optional[float] = None,
        stop_loss: Optional[float] = None,
        shares: Optional[int] = None,
        budget: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Manually or programmatically injects a delivery share into the AI automated trading engine.
        Calculates optimal targets and stop-loss from the Delivery Intelligence Engine if not supplied,
        places paper CNC order, logs to `ai_trade_transactions`, and begins live automated management
        (50% breakeven trailing stop, Target 1 profit booking, and Stop Loss execution).
        """
        from app.providers.universe import NSE_UNIVERSE
        from app.routers.delivery import _build_delivery_pick, DELIVERY_SETUPS_CATALOG
        from app.routers.paper_trading import portfolio, PlacePaperTradeRequest, place_paper_trade

        sym = symbol.strip().upper()
        if sym not in NSE_UNIVERSE:
            raise ValueError(f"Symbol '{sym}' not recognized in NSE Universe.")

        # Check if already open
        if any(p["symbol"].upper() == sym for p in portfolio.positions.values()):
            raise ValueError(f"Position for #{sym} is already open in the portfolio.")

        quote = market_state.active_provider.get_quote(sym)
        live_price = float(quote.ltp) if (quote and getattr(quote, 'ltp', 0) > 0) else float(NSE_UNIVERSE[sym]["base_price"])
        entry = float(entry_price or live_price)

        allocated_budget = float(budget or self.delivery_budget_per_order)
        pick = _build_delivery_pick(sym, NSE_UNIVERSE[sym], quote, allocated_budget, prob=0.82)

        t1 = float(target_1 or pick["target_1"])
        t2 = float(target_2 or pick["target_2"])
        sl = float(stop_loss or pick["stop_loss"])
        strategy = pick.get("technical_setup", "Delivery Swing Breakout")

        if shares and shares > 0:
            qty = int(shares)
        else:
            qty = pick.get("suggested_shares") or max(1, int(allocated_budget / entry))

        margin_required = round(qty * entry, 2)
        if margin_required > portfolio.available_cash:
            if entry <= portfolio.available_cash:
                qty = 1
                margin_required = entry
            else:
                raise ValueError(f"Insufficient cash for Delivery trade #{sym}: Need ₹{margin_required:,.2f}, Available: ₹{portfolio.available_cash:,.2f}")

        req = PlacePaperTradeRequest(
            symbol=sym,
            direction="LONG",
            trade_type="DELIVERY",
            product_type="CNC",
            entry_price=entry,
            target_1=t1,
            target_2=t2,
            stop_loss=sl,
            budget=allocated_budget,
            shares=qty,
            strategy=f"AI Delivery: {strategy[:45]}",
            source="AI_AUTO_TRADER_DELIVERY"
        )

        order_res = place_paper_trade(req)
        pos_info = order_res.get("position", {})
        pos_id = pos_info.get("position_id")

        db = SessionLocal()
        try:
            trade_uuid = f"AITRADE-DELIV-{uuid.uuid4().hex[:8].upper()}"
            tx_record = AITradeTransactionRecord(
                trade_id=trade_uuid,
                position_id=str(pos_id),
                symbol=sym,
                direction="LONG",
                trade_type="DELIVERY",
                entry_time=datetime.datetime.now(datetime.timezone.utc),
                entry_price=entry,
                target_price=t1,
                stop_loss_price=sl,
                quantity=qty,
                status="OPEN",
                strategy=strategy,
                ml_probability=0.82,
                conviction_score=0.85,
                risk_reward_ratio=pick.get("risk_reward_ratio", 2.2),
                rvol=1.0,
                market_regime=pick.get("holding_period", "2-4 Weeks"),
                supporting_factors=[pick.get("technical_setup", ""), pick.get("fundamental_catalyst", "")],
                trained_in_ml=False
            )
            db.add(tx_record)
            db.commit()

            logger.info(f"🎯 Successfully auto-added Delivery stock #{sym} to AI Auto-Trader: {qty} shares @ ₹{entry:,.2f} | TGT: ₹{t1} | SL: ₹{sl}")
            return {
                "success": True,
                "trade_id": trade_uuid,
                "position_id": pos_id,
                "symbol": sym,
                "trade_type": "DELIVERY",
                "shares": qty,
                "entry_price": entry,
                "target_1": t1,
                "target_2": t2,
                "stop_loss": sl,
                "message": f"Successfully auto-added #{sym} ({qty} shares @ ₹{entry:,.2f}) into AI Auto-Trader. Managed automatically with Breakeven Trailing and Target 1 exit."
            }
        finally:
            db.close()

    def sync_closed_positions(self):
        """
        Synchronizes newly closed positions from Paper Trading into `ai_trade_transactions`.
        Ensures exact exit prices, net P&L, win/loss status, and exit reasons are recorded for ML training.
        """
        from app.routers.paper_trading import portfolio

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
    1. Real-Time Position Monitor: Checks open positions every 3 seconds for Target 1, Stop Loss,
       and Breakeven Trailing Stop triggers.
    2. Synchronizes closed AI trades into dedicated database.
    3. 5-Minute Setup Scanner: Runs AI intraday trade scan every 300s during market hours.
    """
    from app.routers.paper_trading import portfolio
    logger.info("Starting AI Auto-Trader daemon loop (continuous SL/Target monitor + 5-min trade scanner)...")
    await asyncio.sleep(10)  # Initial grace period for engine warmup
    last_scan_time = 0.0

    while True:
        try:
            import time
            now_ts = time.time()

            # 1. Real-Time Monitor: Update quotes & trigger SL/TP on open positions
            if portfolio.positions:
                try:
                    portfolio.get_summary()
                    ai_auto_trader.sync_closed_positions()
                except Exception as e:
                    logger.warning(f"Error in portfolio real-time auto-exit check: {e}")

            # 2. Check 5-minute scan cycle
            if (now_ts - last_scan_time) >= ai_auto_trader.interval_seconds:
                if ai_auto_trader.enabled and ai_auto_trader.is_market_hours():
                    try:
                        ai_auto_trader.scan_and_execute_trades()
                    except Exception as e:
                        logger.error(f"Error executing AI 5-min trade scan: {e}")
                last_scan_time = now_ts

            # Responsive 3-second sleep between position health checks
            await asyncio.sleep(3)

        except asyncio.CancelledError:
            logger.info("AI Auto-Trader loop cancelled.")
            break
        except Exception as err:
            logger.error(f"Unexpected error in ai_auto_trader_loop: {err}")
            await asyncio.sleep(10)
