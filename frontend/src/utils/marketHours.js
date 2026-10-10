/**
 * Indian Market Hours Utility
 * NSE/BSE Trading Hours: Mon–Fri, 09:15–15:30 IST (UTC+5:30)
 * Pre-market: 09:00–09:15 IST
 * Post-market: 15:30–16:00 IST
 *
 * Holiday sources: NSE official holiday list
 * Source: https://www.nseindia.com/products-services/equity-market-timings-holidays
 */

// Year-specific NSE Holidays (YYYY-MM-DD format for precision)
// Update this object each year with official NSE holiday list
const NSE_HOLIDAYS_BY_YEAR = {
  2025: [
    '2025-01-26', // Republic Day
    '2025-02-26', // Maha Shivaratri
    '2025-03-14', // Holi
    '2025-04-10', // Id-ul-Fitr (Eid)
    '2025-04-14', // Dr. Ambedkar Jayanti & Good Friday
    '2025-04-18', // Good Friday
    '2025-05-01', // Maharashtra Day
    '2025-08-15', // Independence Day
    '2025-10-02', // Gandhi Jayanti / Mahatma Gandhi's Birthday
    '2025-10-20', // Diwali Laxmi Puja (Muhurat Trading — half day NOT counted)
    '2025-10-21', // Diwali-Balipratipada
    '2025-11-05', // Guru Nanak Jayanti
    '2025-12-25', // Christmas
  ],
  2026: [
    '2026-01-26', // Republic Day
    '2026-03-20', // Holi
    '2026-04-02', // Good Friday
    '2026-04-14', // Dr. Ambedkar Jayanti
    '2026-04-15', // Ram Navami
    '2026-05-01', // Maharashtra Day / Labour Day
    '2026-06-20', // Eid ul-Adha (Bakri Eid) — approx, subject to moon sighting
    '2026-08-15', // Independence Day
    '2026-10-02', // Gandhi Jayanti
    '2026-10-29', // Diwali Laxmi Puja
    '2026-10-30', // Diwali-Balipratipada
    '2026-11-23', // Guru Nanak Jayanti
    '2026-12-25', // Christmas
  ],
};

// Fallback: month-day only (MM-DD) for years not explicitly listed
const NSE_HOLIDAYS_FALLBACK_MMDD = [
  '01-26', // Republic Day
  '04-14', // Dr. Ambedkar Jayanti (approximate — varies)
  '08-15', // Independence Day
  '10-02', // Gandhi Jayanti
  '12-25', // Christmas
];

export function getNowIST() {
  // Convert current UTC to IST (UTC+5:30)
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + 5.5 * 3600000);
}

function isHoliday(istDate) {
  const year = istDate.getFullYear();
  const yyyy = String(year);
  const mm = String(istDate.getMonth() + 1).padStart(2, '0');
  const dd = String(istDate.getDate()).padStart(2, '0');
  const fullDate = `${yyyy}-${mm}-${dd}`;
  const mmdd = `${mm}-${dd}`;

  // Try year-specific list first (most accurate)
  const yearList = NSE_HOLIDAYS_BY_YEAR[year];
  if (yearList) {
    return yearList.includes(fullDate);
  }

  // Fallback to generic MM-DD for unlisted years (only certain fixed holidays)
  return NSE_HOLIDAYS_FALLBACK_MMDD.includes(mmdd);
}

export function isMarketOpen() {
  const forceStatus = localStorage.getItem('trade_intel_force_market_status');
  if (forceStatus === 'OPEN') return true;
  if (forceStatus === 'CLOSED') return false;

  const ist = getNowIST();
  const day = ist.getDay(); // 0=Sun, 1=Mon...6=Sat
  if (day === 0 || day === 6 || isHoliday(ist)) return false; // Weekend or Holiday

  const h = ist.getHours();
  const m = ist.getMinutes();
  const totalMin = h * 60 + m;

  // 09:15 to 15:30 IST
  return totalMin >= 9 * 60 + 15 && totalMin < 15 * 60 + 30;
}

export function isPreMarket() {
  const ist = getNowIST();
  const day = ist.getDay();
  if (day === 0 || day === 6) return false;

  const h = ist.getHours();
  const m = ist.getMinutes();
  const totalMin = h * 60 + m;

  // 09:00 to 09:15
  return totalMin >= 9 * 60 && totalMin < 9 * 60 + 15;
}

export function isPostMarket() {
  const ist = getNowIST();
  const day = ist.getDay();
  if (day === 0 || day === 6) return false;

  const h = ist.getHours();
  const m = ist.getMinutes();
  const totalMin = h * 60 + m;

  // 15:30 to 16:00
  return totalMin >= 15 * 60 + 30 && totalMin < 16 * 60;
}

export function getMarketStatus() {
  const forceStatus = localStorage.getItem('trade_intel_force_market_status');
  if (forceStatus === 'OPEN') return 'OPEN';
  if (forceStatus === 'CLOSED') return 'CLOSED';

  if (isMarketOpen()) return 'OPEN';
  if (isPreMarket()) return 'PRE_MARKET';
  if (isPostMarket()) return 'POST_MARKET';

  const ist = getNowIST();
  const day = ist.getDay();
  if (day === 0 || day === 6) return 'WEEKEND';
  if (isHoliday(ist)) return 'HOLIDAY';
  return 'CLOSED';
}

/**
 * Returns the appropriate refresh interval in milliseconds.
 * 
 * - Market OPEN:      Fast refresh (live trading mode)
 * - PRE/POST-market:  Medium refresh (preparation/analysis mode)
 * - Market CLOSED:    Slow refresh — just keep data warm, don't waste API quota
 * - WEEKEND:          Very slow refresh — no live data to get
 * 
 * @param {number} openMs   - Interval when market is open
 * @param {number} closedMs - Interval when market is closed (default: 5 minutes)
 * @param {number} weekendMs - Interval on weekends (default: 15 minutes)
 */
export function getSmartInterval(openMs, closedMs = 5 * 60000, weekendMs = 15 * 60000) {
  const status = getMarketStatus();
  if (status === 'OPEN') return openMs;
  if (status === 'PRE_MARKET' || status === 'POST_MARKET') return Math.max(openMs * 3, 30000);
  if (status === 'WEEKEND') return weekendMs;
  return closedMs; // CLOSED (weeknight)
}

export function getMarketStatusLabel() {
  const status = getMarketStatus();
  const ist = getNowIST();
  const timeStr = ist.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata', hour12: false });

  switch (status) {
    case 'OPEN':       return { label: `🟢 Market Open`, color: 'text-emerald-400', status };
    case 'PRE_MARKET': return { label: `🟡 Pre-Market (${timeStr} IST)`, color: 'text-amber-400', status };
    case 'POST_MARKET':return { label: `🟠 Post-Market`, color: 'text-orange-400', status };
    case 'WEEKEND':    return { label: `⚫ Weekend — Market Closed`, color: 'text-slate-500', status };
    case 'HOLIDAY':    return { label: `🔵 Public Holiday — Market Closed`, color: 'text-blue-400', status };
    default:           return { label: `🔴 Market Closed`, color: 'text-rose-400', status };
  }
}
