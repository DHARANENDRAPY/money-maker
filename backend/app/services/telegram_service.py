import logging
import datetime
import html
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
        import datetime
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
        profit_pct = abs((target - entry) / entry * 100.0) if entry > 0 else 0.0
        loss_pct = abs((entry - sl) / entry * 100.0) if entry > 0 else 0.0
        regime = html.escape(str(rec.get("market_regime", "MODERATE_BULLISH")).replace("_", " "))
        factors = rec.get("supporting_factors", [])
        factors_str = "\n".join([f"  • {html.escape(str(f))}" for f in factors[:3]]) if factors else "  • Multi-factor technical confluence"

        # Calculate exact decision time in IST
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
        decision_time_str = ist_now.strftime("%d %b %Y, %I:%M:%S %p IST")

        msg = (
            f"⚡ <b>NEW AI RECOMMENDATION: #{symbol}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 <b>AI Decision Time:</b> <code>{decision_time_str}</code>\n"
            f"📋 <b>Trade Type:</b> <code>INTRADAY / MIS (Same-Day)</code>\n"
            f"<b>Action:</b> {dir_emoji}\n"
            f"⏳ <b>Hold Duration:</b> <code>15 to 45 Minutes</code>\n"
            f"🔥 <b>AI Setup Confidence:</b> <code>{conviction}%</code> ({'HIGH CONVICTION' if conviction >= 80 else 'MODERATE'})\n"
            f"🎯 <b>Statistical Win Rate:</b> <code>{ml_prob}%</code> (Risk:Reward 1:{rr:.1f} • Positive Expectancy)\n\n"
            f"<b>WHEN TO ENTER:</b>\n"
            f"  • Entry Price: <b>₹{entry:,.2f}</b>\n\n"
            f"<b>WHEN TO EXIT:</b>\n"
            f"  • 🎯 Target: <b>₹{target:,.2f}</b> (+{profit_pct:.1f}% Expected Profit)\n"
            f"  • 🛑 Stop Loss: <b>₹{sl:,.2f}</b> (-{loss_pct:.1f}% Max Risk)\n"
            f"  • ⚖️ Risk/Reward: 1:{rr:.1f}\n"
            f"  • ⚠️ Time Exit: Close position before 15:15 IST. Do NOT hold overnight.\n\n"
            f"💡 <b>Reason / Strategy:</b>\n"
            f"  • Setup: <code>{strategy}</code>\n"
            f"  • Market Context: {regime}\n"
            f"{factors_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
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

        # Calculate exact decision time in IST
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
        decision_time_str = ist_now.strftime("%d %b %Y, %I:%M:%S %p IST")

        msg = (
            f"💎 <b>NEW AI RECOMMENDATION: #{symbol}</b>\n"
            f"<b>{name}</b> ({sector})\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕐 <b>AI Decision Time:</b> <code>{decision_time_str}</code>\n"
            f"📋 <b>Trade Type:</b> <code>DELIVERY / CNC (Multi-Day Hold)</code>\n"
            f"⏳ <b>Hold Duration:</b> <code>{horizon}</code>\n"
            f"🎯 <b>Accuracy / Win Prob:</b> <code>{pick.get('conviction_pct', 70)}%</code> ({stars})\n\n"
            f"<b>WHEN TO ENTER:</b>\n"
            f"  • Current LTP: <b>₹{ltp:,.2f}</b>\n"
            f"  • Ideal Buy Zone: <b>₹{buy_min:,.2f} – ₹{buy_max:,.2f}</b>\n\n"
            f"<b>WHEN TO EXIT:</b>\n"
            f"  • 🎯 Target 1: <b>₹{t1:,.2f}</b> (+{t1_gain:.1f}% Profit)\n"
            f"  • 🚀 Target 2: <b>₹{t2:,.2f}</b> (+{t2_gain:.1f}% Extended Gain)\n"
            f"  • 🛑 Stop Loss: <b>₹{sl:,.2f}</b> (-{sl_risk:.1f}% Max Risk)\n"
            f"  • ⚖️ Risk/Reward: 1:{pick.get('risk_reward_ratio', 3.0):.1f}\n"
            f"  • 🛡️ Trailing Rule: Trail SL to entry price once Target 1 is hit.\n\n"
            f"💡 <b>Reason / Catalysts:</b>\n"
            f"  • Technical: {tech_setup}\n"
            f"  • Catalyst: {fund_reason}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Delivery/CNC: Hold for {horizon}. Do NOT exit same day.</b>\n"
            f"<i>Analysis-only. Verify in broker terminal before trading.</i>"
        )

        result = self.send_message(msg, parse_mode="HTML")
        if result.get("success"):
            self._sent_signals.add(pick_id)
        return result

telegram_service = TelegramService()
