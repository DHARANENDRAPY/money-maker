# Trade Intelligence AI — Intraday Trading Analysis Platform

An intelligent, real-time intraday market analysis and trade-opportunity discovery platform engineered specifically for **Indian Stock Markets (NSE)**.

> **CRITICAL DISCLAIMER**: This is an **analysis-only platform**. It **NEVER places, modifies, or executes real orders**. The user retains complete authority and responsibility to execute trades manually via their own regulated broker terminal.

---

## 🚀 Key Features

### 1. 12-Factor Multi-Dimensional Analysis Engine
Evaluates every stock independently across twelve distinct quant and market factors:
1. **Overall Market Trend**: Nifty 50 momentum, EMAs, Advance/Decline breadth, and regime classification (*Strong Bullish, Moderate Bullish, Sideways, Moderate Bearish, Uncertain*).
2. **Sector Performance & Relative Strength**: Intra-day sector returns vs. Nifty 50 spread and momentum score.
3. **News & Event Intelligence**: Extensible NLP sentiment scoring (-1.0 to +1.0) and corporate action / policy / earnings tagging.
4. **Price Action**: Previous Day High/Low (PDH/PDL), 15m Opening Range Breakout (ORB), Pivot Points, and wick rejections.
5. **Volume & Order Flow**: Relative Volume (RVOL), volume expansion spikes, and depth dominance proxy.
6. **Volatility & Feasibility**: ATR(14), realized intraday expansion ranges, and uncertainty bounds.
7. **Liquidity & Execution**: Bid-ask spread % penalty, turnover in Crores, and slippage estimation.
8. **Time-of-Day Seasonality**: Indian market temporal windows (Opening Discovery 09:15-09:45, Prime Trend 09:45-11:30, Midday Chop 11:30-13:30, Afternoon Expansion 13:30-15:00, MIS Square-Off 15:00-15:30).
9. **Technical Indicators**: VWAP, EMA 9/21 crossovers, RSI 14 Wilder momentum zones, and MACD histograms.
10. **Risk Management Geometry**: Stop-Loss, Target price feasibility, and strict $\ge 1:1.5$ Risk/Reward constraint.
11. **Data Freshness & Latency**: Real-time tick latency tracking and stale feed invalidation.
12. **Trader Discipline Context**: Behavioral guardrails against revenge trading, overtrading, and plan deviation.

---

### 2. Machine Learning Probability Estimator
- **Objective**: Given an intraday entry trigger, stop-loss, target, and holding horizon, estimates the calibrated probability that target is reached before stop-loss.
- **Validation**: Walk-forward temporal train/test split with zero lookahead bias.
- **Calibration**: Platt sigmoid scaling with Reliability Curve visualization (Predicted Probability vs Empirical True Win Frequency).
- **Conservative Touch Rule**: If both Target and Stop Loss are breached within the exact same candle, it is conservatively scored as a Stop-Loss hit.

---

### 3. Indian Statutory Charges & Position Sizer
Calculates exact real-world transaction costs for NSE Equity Intraday:
- **Brokerage**: ₹20 flat or 0.03%
- **STT (Securities Transaction Tax)**: 0.025% on sell turnover
- **Exchange Txn Fee**: 0.00297% (NSE)
- **GST**: 18% on (Brokerage + Exchange Txn + SEBI)
- **SEBI Turnover Fee**: ₹10 per Crore (0.0001%)
- **Stamp Duty**: 0.003% on buy value
- **Breakeven Points**: Exact points movement required to clear all taxes.
- **Position Sizing**: Automatically sizes share quantity to respect the user's max monetary risk and 50% intraday portfolio exposure ceiling.

---

### 4. Modular Market Data Provider (Demo & Angel One SmartAPI)
- **Demo Mode (Default)**: High-fidelity realistic synthetic intraday simulator for 20+ NSE stocks (RELIANCE, INFY, HDFCBANK, TCS, ICICIBANK, TATAMOTORS, etc.). Clearly marked with yellow status badges.
- **Angel One SmartAPI Provider**: Dedicated backend provider module with TOTP authentication, instrument master resolution, historical candle endpoints, and WebSocket streaming.

---

## 🛠️ Technology Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons, TradingView Lightweight Charts
- **Backend**: Python 3.13, FastAPI, Uvicorn, Pandas, NumPy, Scikit-learn, SQLAlchemy
- **Database**: SQLite (Repository pattern ready for PostgreSQL migration)
- **Real-Time Feed**: WebSockets (`/ws`)

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js v18+ & npm

### 1. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Run backend tests
python -m pytest tests -v

# Start FastAPI backend server (port 8000)
python run.py
```
Backend API docs available at: `http://127.0.0.1:8000/docs`

---

### 2. Frontend Setup
```bash
# Navigate to frontend directory in a new terminal
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (port 5173)
npm run dev
```
Open browser at: `http://localhost:5173`

---

## ⚙️ Configuration (.env)

Copy `.env.example` to `.env`:
```env
APP_NAME="Trade Intelligence AI"
PORT=8000
DATA_PROVIDER="demo" # or "angel_one"
ANGEL_API_KEY="your_smartapi_key"
ANGEL_CLIENT_CODE="your_client_code"
ANGEL_PIN="your_pin"
ANGEL_TOTP_SECRET="your_totp_secret"
```

---

## 🧪 Running Automated Tests

```bash
cd backend
python -m pytest tests -v
```
Tests cover:
- Indicator calculations (VWAP, EMA, RSI, MACD, ATR, Supertrend, RVOL, Key levels)
- Indian statutory cost breakdowns and breakeven point calculation
- Position sizing limits and risk allocation
- 12-factor evaluation engine
- ML feature extraction without lookahead bias
- Target-before-stop outcome labelling & walk-forward calibration
