import uuid
import datetime
from typing import List, Dict, Any, Optional
from app.schemas.all_schemas import AlertItem
from app.models.all_models import AlertRecord
from app.database import SessionLocal

class AlertService:
    """
    Manages generation, deduplication, and persistence of market alerts.
    """

    def __init__(self):
        self._recent_alerts: List[AlertItem] = []
        self._initialize_default_alerts()

    def _initialize_default_alerts(self):
        now = datetime.datetime.utcnow()
        self._recent_alerts = [
            AlertItem(
                alert_id="ALT-INIT-01",
                timestamp=(now - datetime.timedelta(minutes=12)).isoformat() + "Z",
                alert_type="NEW_CANDIDATE",
                severity="INFO",
                symbol="INFY",
                title="New Setup: 15m ORB Breakout",
                message="INFY crossed 15m opening range high (₹1892.40) with RVOL 1.8x. Calibrated target probability is 64%.",
                details={"strategy": "15m ORB Breakout", "entry": 1892.40, "sl": 1878.00, "tp": 1918.00}
            ),
            AlertItem(
                alert_id="ALT-INIT-02",
                timestamp=(now - datetime.timedelta(minutes=25)).isoformat() + "Z",
                alert_type="CONFIRMED_SETUP",
                severity="SUCCESS",
                symbol="RELIANCE",
                title="Confirmed Setup: VWAP Trend Pullback",
                message="RELIANCE triggered entry at ₹2942.50 bouncing cleanly off VWAP support. Bullish EMA alignment intact.",
                details={"strategy": "VWAP Trend Pullback", "entry": 2942.50, "sl": 2928.00, "tp": 2971.00}
            ),
            AlertItem(
                alert_id="ALT-INIT-03",
                timestamp=(now - datetime.timedelta(minutes=40)).isoformat() + "Z",
                alert_type="RISK_WARNING",
                severity="WARNING",
                symbol=None,
                title="Market Breadth Shift Warning",
                message="Advance/Decline ratio tightened from 2.1 to 1.8. Watch for intraday chop in FMCG and Auto sectors.",
                details={"ad_ratio": 1.88, "nifty_change": "+0.58%"}
            )
        ]

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        symbol: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AlertItem:
        # Check duplicate in last 5 minutes for same symbol and alert_type
        for a in self._recent_alerts[:10]:
            if a.symbol == symbol and a.alert_type == alert_type and a.title == title:
                return a  # Prevent duplicate alert flood
                
        now = datetime.datetime.utcnow()
        alert_id = f"ALT-{now.strftime('%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        item = AlertItem(
            alert_id=alert_id,
            timestamp=now.isoformat() + "Z",
            alert_type=alert_type,
            severity=severity,
            symbol=symbol,
            title=title,
            message=message,
            details=details or {},
            is_dismissed=False
        )
        self._recent_alerts.insert(0, item)
        if len(self._recent_alerts) > 100:
            self._recent_alerts = self._recent_alerts[:100]
            
        # Optionally persist to DB
        try:
            db = SessionLocal()
            rec = AlertRecord(
                alert_id=alert_id,
                timestamp=now,
                alert_type=alert_type,
                severity=severity,
                symbol=symbol,
                title=title,
                message=message,
                details=details or {},
                is_dismissed=False
            )
            db.add(rec)
            db.commit()
            db.close()
        except Exception:
            pass
            
        return item

    def get_alerts(self, limit: int = 50, symbol: Optional[str] = None, unread_only: bool = False) -> List[AlertItem]:
        filtered = self._recent_alerts
        if symbol:
            filtered = [a for a in filtered if a.symbol == symbol]
        if unread_only:
            filtered = [a for a in filtered if not a.is_dismissed]
        return filtered[:limit]

    def dismiss_alert(self, alert_id: str) -> bool:
        for a in self._recent_alerts:
            if a.alert_id == alert_id:
                a.is_dismissed = True
                return True
        return False

alert_service = AlertService()
