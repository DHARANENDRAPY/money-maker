"""
Live Market News Provider
Fetches real-time financial news from publicly available Indian market RSS feeds.
Sources: Economic Times, Moneycontrol, Business Standard, LiveMint, NSE India.

Falls back to an empty list on failure — never shows stale hardcoded headlines.
"""
import datetime
import logging
import threading
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict
from app.schemas.all_schemas import NewsItem

logger = logging.getLogger("news_provider")

# NSE symbol keyword mapping for tagging news to stocks
_SYMBOL_KEYWORDS: Dict[str, List[str]] = {
    "RELIANCE":    ["reliance", "ril", "jio", "mukesh ambani"],
    "TCS":         ["tcs", "tata consultancy"],
    "INFY":        ["infosys", "infy"],
    "HDFCBANK":    ["hdfc bank", "hdfcbank"],
    "ICICIBANK":   ["icici bank", "icicibank"],
    "SBIN":        ["sbi", "state bank"],
    "WIPRO":       ["wipro"],
    "TATAMOTORS":  ["tata motors", "tatamotors", "jlr", "jaguar"],
    "TATASTEEL":   ["tata steel", "tatasteel"],
    "ONGC":        ["ongc", "oil and natural gas"],
    "GAIL":        ["gail"],
    "IOC":         ["ioc", "indian oil"],
    "BHEL":        ["bhel", "bharat heavy"],
    "BEL":         ["bel", "bharat electronics"],
    "SUZLON":      ["suzlon"],
    "NHPC":        ["nhpc"],
    "IRFC":        ["irfc", "indian railway finance"],
    "ZOMATO":      ["zomato", "blinkit"],
    "IDFCFIRSTB":  ["idfc first", "idfcfirstb"],
    "PNB":         ["pnb", "punjab national"],
    "TATAPOWER":   ["tata power"],
    "HCLTECH":     ["hcl tech", "hcltech"],
    "AXISBANK":    ["axis bank", "axisbank"],
    "KOTAKBANK":   ["kotak mahindra", "kotak bank"],
    "ASIANPAINT":  ["asian paints", "asianpaint"],
    "MARUTI":      ["maruti", "suzuki"],
    "ITC":         ["itc ltd", "itc limited"],
    "TITAN":       ["titan"],
    "BAJFINANCE":  ["bajaj finance", "bajfinance"],
}

_SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "Information Tech": ["it sector", "software", "tech", "nasdaq", "ai", "cloud"],
    "Banking & Fin":    ["rbi", "repo rate", "banking", "nbfc", "credit", "npa", "loan"],
    "Energy & Oil":     ["crude", "oil", "brent", "opec", "petrol", "diesel", "gas price"],
    "Automobiles":      ["auto sales", "ev", "electric vehicle", "automobile", "vehicle"],
    "FMCG":             ["fmcg", "consumer goods", "rural demand", "inflation"],
    "Metals":           ["steel", "copper", "aluminium", "metal", "iron ore"],
    "Pharma":           ["pharma", "drug", "fda", "usfda", "medicine"],
    "Defence":          ["defence", "defense", "military", "drdo", "ordnance"],
    "Power & Infra":    ["power", "electricity", "renewable", "wind", "solar", "infra"],
    "Real Estate":      ["real estate", "realty", "housing", "rera", "property"],
}

RSS_FEEDS = [
    {
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "source": "Economic Times Markets",
    },
    {
        "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
        "source": "Economic Times Stocks",
    },
    {
        "url": "https://www.livemint.com/rss/markets",
        "source": "LiveMint",
    },
    {
        "url": "https://www.livemint.com/rss/companies",
        "source": "LiveMint Companies",
    },
    {
        "url": "https://economictimes.indiatimes.com/markets/mutual-funds/rssfeeds/1052732061.cms",
        "source": "Economic Times MF & Investment",
    },
    {
        "url": "https://economictimes.indiatimes.com/markets/commodities/rssfeeds/1052732059.cms",
        "source": "Economic Times Commodities",
    },
]

# Maximum age of news to show (in hours)
_MAX_NEWS_AGE_HOURS = 24


def _classify_sentiment(text: str) -> tuple[str, float]:
    """Simple keyword-based sentiment classifier."""
    text_l = text.lower()
    positive_kw = [
        "surge", "gain", "rally", "record", "beat", "strong", "growth", "profit",
        "deal", "expansion", "bullish", "upgrade", "buyback", "dividend", "win",
        "breakout", "recovery", "positive", "increase", "rise", "up", "soar"
    ]
    negative_kw = [
        "fall", "decline", "loss", "miss", "weak", "drop", "bearish", "downgrade",
        "cut", "concern", "risk", "warning", "crash", "slump", "down", "fear",
        "npa", "default", "sell-off", "negative", "pressure", "disappoints"
    ]
    pos = sum(1 for kw in positive_kw if kw in text_l)
    neg = sum(1 for kw in negative_kw if kw in text_l)

    if pos > neg + 1:
        score = min(0.95, 0.55 + pos * 0.05)
        return "POSITIVE", round(score, 2)
    elif neg > pos + 1:
        score = max(-0.95, -(0.55 + neg * 0.05))
        return "NEGATIVE", round(score, 2)
    return "NEUTRAL", 0.05


def _classify_impact(text: str) -> str:
    text_l = text.lower()
    high_kw = ["rbi", "fed", "budget", "result", "earnings", "q2", "q3", "q4", "ipo", "merger", "acquisition"]
    if any(kw in text_l for kw in high_kw):
        return "HIGH"
    medium_kw = ["target", "upgrade", "downgrade", "deal", "expansion", "capex", "order"]
    if any(kw in text_l for kw in medium_kw):
        return "MEDIUM"
    return "LOW"


def _tag_symbols(text: str) -> List[str]:
    text_l = text.lower()
    return [sym for sym, kws in _SYMBOL_KEYWORDS.items() if any(kw in text_l for kw in kws)]


def _tag_sectors(text: str) -> List[str]:
    text_l = text.lower()
    return [sec for sec, kws in _SECTOR_KEYWORDS.items() if any(kw in text_l for kw in kws)]


def _parse_feed_date(date_str: str) -> Optional[datetime.datetime]:
    """Parses common RSS date formats."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _fetch_rss_feed(feed_info: dict) -> List[NewsItem]:
    """Fetches and parses a single RSS feed into NewsItem objects."""
    try:
        import urllib.request
        req = urllib.request.Request(
            feed_info["url"],
            headers={"User-Agent": "MoneyMakerAI/1.0 (financial-news-aggregator)"}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        channel = root.find("channel")
        if channel is None:
            channel = root

        items = channel.findall("item")
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now_utc - datetime.timedelta(hours=_MAX_NEWS_AGE_HOURS)

        news_items: List[NewsItem] = []
        for i, item in enumerate(items[:20]):
            title_el = item.find("title")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")
            link_el = item.find("link")

            headline = title_el.text.strip() if title_el is not None and title_el.text else ""
            summary = desc_el.text.strip() if desc_el is not None and desc_el.text else headline
            # Strip HTML tags from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary)[:300]

            if not headline:
                continue

            pub_str = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else ""
            pub_dt = _parse_feed_date(pub_str) if pub_str else now_utc
            if pub_dt and pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)

            # Skip stale news
            if pub_dt and pub_dt < cutoff:
                continue

            combined_text = f"{headline} {summary}"
            sentiment, score = _classify_sentiment(combined_text)
            impact = _classify_impact(combined_text)
            symbols = _tag_symbols(combined_text)
            sectors = _tag_sectors(combined_text)

            ts = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_dt else now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            news_items.append(NewsItem(
                news_id=f"LIVE-{feed_info['source'][:4].upper()}-{abs(hash(headline)) % 100000:05d}",
                timestamp=ts,
                source=feed_info["source"],
                headline=headline,
                summary=summary,
                sentiment=sentiment,
                sentiment_score=score,
                impact_level=impact,
                affected_symbols=symbols,
                affected_sectors=sectors,
                category="LIVE_FEED"
            ))

        return news_items
    except Exception as e:
        logger.warning(f"Failed to fetch RSS from {feed_info['source']}: {e}")
        return []


class NewsProvider:
    """
    Real-time Indian financial news aggregator.
    Polls multiple RSS feeds every 5 minutes and caches results in memory.
    Returns empty list on failure \u2014 NEVER shows static hardcoded data.
    """

    REFRESH_INTERVAL_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._cache: List[NewsItem] = []
        self._last_refresh: Optional[datetime.datetime] = None
        self._lock = threading.Lock()
        # Eager initial load in background so first request is fast
        t = threading.Thread(target=self._refresh, daemon=True)
        t.start()

    def _refresh(self):
        """Fetches all RSS feeds and updates cache."""
        all_items: List[NewsItem] = []
        for feed in RSS_FEEDS:
            all_items.extend(_fetch_rss_feed(feed))

        # De-duplicate by headline, sort by timestamp desc
        seen: set = set()
        unique: List[NewsItem] = []
        for item in all_items:
            key = item.headline[:60].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)

        unique.sort(key=lambda x: x.timestamp, reverse=True)

        with self._lock:
            self._cache = unique[:50]
            self._last_refresh = datetime.datetime.utcnow()

        logger.info(f"NewsProvider: refreshed {len(self._cache)} live articles from {len(RSS_FEEDS)} RSS feeds")

    def _maybe_refresh(self):
        """Refresh cache if stale (older than REFRESH_INTERVAL_SECONDS)."""
        if (self._last_refresh is None or
                (datetime.datetime.utcnow() - self._last_refresh).total_seconds() > self.REFRESH_INTERVAL_SECONDS):
            t = threading.Thread(target=self._refresh, daemon=True)
            t.start()

    def get_latest_news(self, limit: int = 10, symbol: Optional[str] = None, sector: Optional[str] = None) -> List[NewsItem]:
        self._maybe_refresh()
        with self._lock:
            filtered = list(self._cache)

        if symbol:
            filtered = [n for n in filtered if symbol.upper() in n.affected_symbols]
        if sector:
            filtered = [n for n in filtered if sector.lower() in [s.lower() for s in n.affected_sectors]]

        return filtered[:limit]

    def add_news(self, news: NewsItem):
        """Manually inject a news item (e.g., from NSE announcements webhook)."""
        with self._lock:
            self._cache.insert(0, news)

    def get_status(self) -> dict:
        return {
            "last_refresh": self._last_refresh.isoformat() + "Z" if self._last_refresh else None,
            "cached_articles": len(self._cache),
            "feeds": [f["source"] for f in RSS_FEEDS],
            "refresh_interval_minutes": self.REFRESH_INTERVAL_SECONDS // 60,
        }
