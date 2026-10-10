import logging
import requests
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("telegram_service")

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = settings.TELEGRAM_ENABLED
        self._sent_signals = set()

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled and self.bot_token and self.chat_id),
            "has_token": bool(self.bot_token),
            "has_chat_id": bool(self.chat_id),
            "chat_id": self.chat_id if self.chat_id else "",
            "bot_configured": bool(self.bot_token and len(self.bot_token) > 10)
        }

    def update_config(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()
        self.enabled = enabled
        logger.info(f"Telegram config updated. Enabled: {self.enabled}")

    def send_message(self, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        if not self.bot_token or not self.chat_id:
            return {"success": False, "error": "Telegram Bot Token or Chat ID is missing."}

        import json
        import urllib.request
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "TradeIntelAI/1.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return {"success": True, "message_id": data.get("result", {}).get("message_id")}
                else:
                    err = data.get("description", "Failed to send Telegram message.")
                    logger.error(f"Telegram API error: {err}")
                    return {"success": False, "error": err}
        except Exception as e:
            logger.error(f"Telegram delivery failed: {e}")
            return {"success": False, "error": str(e)}

    def send_test_alert(self) -> Dict[str, Any]:
        msg = (
            "🔔 <b>Trade Intel AI — Test Alert</b>\n\n"
            "✅ Your Telegram notifications are <b>successfully connected</b>!\n\n"
            "Whenever the AI discovers high-conviction intraday setups or top trade picks, "
            "you will instantly receive full trade plans (Entry, Target, Stop Loss, R:R) right here."
        )
        return self.send_message(msg, parse_mode="HTML")

    def send_recommendation_alert(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        signal_id = rec.get("signal_id") or f"{rec.get('symbol')}-{rec.get('direction')}"
        if signal_id in self._sent_signals:
            return {"success": True, "already_sent": True}

        if not self.enabled or not self.bot_token or not self.chat_id:
            return {"success": False, "error": "Telegram alerts disabled or not configured."}

        import html
        symbol = html.escape(str(rec.get("symbol", "N/A")))
        direction = rec.get("direction", "LONG")
        dir_emoji = "🟢 <b>BUY / LONG</b>" if direction == "LONG" else "🔴 <b>SELL / SHORT</b>"
        strategy = html.escape(str(rec.get("strategy", "AI Algorithmic Setup")))
        entry = rec.get("entry_price", 0.0)
        target = rec.get("target_price", 0.0)
        sl = rec.get("stop_loss", 0.0)
        rr = rec.get("risk_reward_ratio", 0.0)
        ml_prob = int((rec.get("ml_probability") or 0.5) * 100)
        conviction = int((rec.get("conviction_score") or 0.5) * 100)
        regime = html.escape(str(rec.get("market_regime", "MODERATE_BULLISH")).replace("_", " "))
        factors = rec.get("supporting_factors", [])
        factors_str = "\n".join([f"  • {html.escape(str(f))}" for f in factors[:3]]) if factors else "  • Multi-factor technical confluence"

        msg = (
            f"⚡ <b>NEW AI INTRADAY PICK: #{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Action:</b> {dir_emoji}\n"
            f"<b>Strategy:</b> <code>{strategy}</code>\n\n"
            f"🎯 <b>Entry:</b> ₹{entry:,.2f}\n"
            f"🎯 <b>Target:</b> ₹{target:,.2f}\n"
            f"🛑 <b>Stop Loss:</b> ₹{sl:,.2f}\n"
            f"⚖️ <b>Risk/Reward:</b> 1:{rr:.1f}\n\n"
            f"🤖 <b>AI Win Probability:</b> <code>{ml_prob}%</code>\n"
            f"⭐ <b>Conviction Score:</b> <code>{conviction}%</code>\n"
            f"🌐 <b>Market Regime:</b> {regime}\n\n"
            f"<b>Key Catalysts:</b>\n{factors_str}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Analysis-only. Verify in broker terminal before trading.</i>"
        )

        result = self.send_message(msg, parse_mode="HTML")
        if result.get("success"):
            self._sent_signals.add(signal_id)
        return result

    def send_delivery_alert(self, pick: Dict[str, Any]) -> Dict[str, Any]:
        pick_id = f"DELIVERY-{pick.get('symbol')}-{pick.get('horizon_code', 'SWING')}"
        if pick_id in self._sent_signals:
            return {"success": True, "already_sent": True}

        if not self.enabled or not self.bot_token or not self.chat_id:
            return {"success": False, "error": "Telegram alerts disabled or not configured."}

        import html
        symbol = html.escape(str(pick.get("symbol", "N/A")))
        name = html.escape(str(pick.get("name", "")))
        sector = html.escape(str(pick.get("sector", "")))
        ltp = pick.get("ltp", 0.0)
        buy_min = pick.get("buy_zone_min", ltp * 0.98)
        buy_max = pick.get("buy_zone_max", ltp * 1.01)
        t1 = pick.get("target_1", 0.0)
        t1_gain = pick.get("target_1_gain_pct", 0.0)
        t2 = pick.get("target_2", 0.0)
        t2_gain = pick.get("target_2_gain_pct", 0.0)
        sl = pick.get("stop_loss", 0.0)
        sl_risk = pick.get("stop_loss_risk_pct", 0.0)
        horizon = html.escape(str(pick.get("holding_period", "2-4 Weeks")))
        stars = "⭐" * int(pick.get("stars", 5))
        tech_setup = html.escape(str(pick.get("technical_setup", "Breakout Setup")))
        fund_reason = html.escape(str(pick.get("fundamental_catalyst", "Strong financial growth")))
        shares_1k = pick.get("shares_for_1k", 1)
        prof_1k = pick.get("profit_t1_for_1k", 0.0)
        loss_1k = pick.get("loss_for_1k", 0.0)

        msg = (
            f"💎 <b>AI DELIVERY & SWING PICK: #{symbol}</b>\n"
            f"<b>{name}</b> ({sector})\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>Rating:</b> {stars} ({pick.get('conviction_pct', 85)}% Conviction)\n"
            f"⏳ <b>Holding Period:</b> <code>{horizon}</code>\n"
            f"📊 <b>Current Price:</b> ₹{ltp:,.2f}\n\n"
            f"🛒 <b>BUY ZONE:</b> ₹{buy_min:,.2f} – ₹{buy_max:,.2f}\n\n"
            f"🎯 <b>Target 1 (Swing):</b> ₹{t1:,.2f} (<b>+{t1_gain:.1f}%</b>)\n"
            f"🚀 <b>Target 2 (Positional):</b> ₹{t2:,.2f} (<b>+{t2_gain:.1f}%</b>)\n"
            f"🛑 <b>Stop Loss:</b> ₹{sl:,.2f} (<b>-{sl_risk:.1f}%</b>)\n"
            f"⚖️ <b>Risk:Reward:</b> 1:{pick.get('risk_reward_ratio', 3.0):.1f}\n\n"
            f"💰 <b>Plan For ₹1,000 Budget:</b>\n"
            f"  • Buy Qty: <b>{shares_1k} shares</b> (Invest: ₹{shares_1k * ltp:,.0f})\n"
            f"  • Target 1 Profit: <font color='#00ff00'><b>+₹{prof_1k:,.0f}</b></font>\n"
            f"  • Max Risk at SL: <font color='#ff0000'><b>-₹{loss_1k:,.0f}</b></font>\n\n"
            f"📈 <b>Technical Setup:</b>\n  • {tech_setup}\n\n"
            f"🏢 <b>Fundamental Catalyst:</b>\n  • {fund_reason}\n\n"
            f"🛡️ <b>Exit Rule:</b> Move SL to cost price once Target 1 is hit. Trail 20-day EMA.\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Delivery / CNC order. Hold with patience according to timeframe.</i>"
        )

        result = self.send_message(msg, parse_mode="HTML")
        if result.get("success"):
            self._sent_signals.add(pick_id)
        return result

telegram_service = TelegramService()
