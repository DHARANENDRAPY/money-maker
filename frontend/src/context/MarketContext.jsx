import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { 
  fetchOverview, 
  fetchAlerts, 
  dismissAlert, 
  toggleWatchlist as apiToggleWatchlist, 
  fetchPaperPortfolio,
  WS_URL 
} from '../services/api';
import { audioAlerts } from '../utils/audioAlerts';
import { isMarketOpen, isPreMarket, isPostMarket, getMarketStatusLabel, getMarketStatus } from '../utils/marketHours';

const MarketContext = createContext();

export const MarketProvider = ({ children }) => {
  const [overview, setOverview] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [unreadAlertsCount, setUnreadAlertsCount] = useState(0);
  const [selectedSymbol, setSelectedSymbol] = useState('RELIANCE');
  const [watchlist, setWatchlist] = useState(['RELIANCE', 'INFY', 'HDFCBANK', 'ICICIBANK', 'TATAMOTORS', 'TCS', 'SBIN']);
  const [isLiveWsConnected, setIsLiveWsConnected] = useState(false);
  const [activeTab, setActiveTab] = useState('recommendations');
  const [isAlertDrawerOpen, setIsAlertDrawerOpen] = useState(false);
  const [isPaperDrawerOpen, setIsPaperDrawerOpen] = useState(false);
  const [lastTick, setLastTick] = useState(null);
  const [liveQuotes, setLiveQuotes] = useState({});
  const [toast, setToast] = useState(null);
  const [marketStatus, setMarketStatus] = useState(() => getMarketStatusLabel());
  const pollingIntervalRef = useRef(null);
  
  // Simple Mode vs Pro Mode
  const [uiMode, setUiMode] = useState(() => localStorage.getItem('trade_intel_ui_mode') || 'simple');
  
  // Audio Mute state
  const [isAudioMuted, setIsAudioMuted] = useState(() => audioAlerts.isMuted);

  // Master Live Feed Toggle (Developer Choice)
  const [isMasterFeedActive, setIsMasterFeedActive] = useState(() => localStorage.getItem('trade_intel_master_feed') !== 'false');

  // Live Paper Trading Portfolio
  const [paperPortfolio, setPaperPortfolio] = useState(null);

  const toggleUiMode = () => {
    const next = uiMode === 'simple' ? 'pro' : 'simple';
    setUiMode(next);
    localStorage.setItem('trade_intel_ui_mode', next);
    showToast(next === 'simple' ? '⚡ Switched to Simple Mode' : '🔬 Switched to Pro Quantitative Mode');
  };

  const toggleAudio = () => {
    const muted = audioAlerts.toggleMute();
    setIsAudioMuted(muted);
    showToast(muted ? '🔕 Audio Alerts Muted' : '🔔 Audio Chimes & Voice Enabled');
  };

  const toggleMasterFeed = () => {
    setIsMasterFeedActive(prev => {
      const next = !prev;
      localStorage.setItem('trade_intel_master_feed', next);
      showToast(next ? '▶️ Live API Fetching Started' : '⏸ Live Feed Paused (API Sleeping)', next ? 'success' : 'info');
      return next;
    });
  };

  const refreshPaperPortfolio = useCallback(async () => {
    try {
      const data = await fetchPaperPortfolio();
      setPaperPortfolio(data);
    } catch {
      // ignore in initial boot
    }
  }, []);

  const showToast = (message, type = 'info') => {
    setToast({ message, type, id: Date.now() });
    setTimeout(() => setToast(null), 4000);
  };

  const refreshOverview = useCallback(async () => {
    try {
      const data = await fetchOverview();
      setOverview(data);
    } catch (err) {
      console.warn('Overview fetch error:', err);
    }
  }, []);

  const refreshAlerts = useCallback(async () => {
    try {
      const data = await fetchAlerts(false);
      setAlerts(data);
      setUnreadAlertsCount(data.filter(a => !a.is_dismissed).length);
    } catch (err) {
      console.warn('Alerts fetch error:', err);
    }
  }, []);

  const handleDismissAlert = async (alertId) => {
    try {
      await dismissAlert(alertId);
      setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, is_dismissed: true } : a));
      setUnreadAlertsCount(prev => Math.max(0, prev - 1));
    } catch (err) {
      console.error(err);
    }
  };

  const toggleWatchlistSymbol = async (symbol) => {
    try {
      const res = await apiToggleWatchlist(symbol);
      if (res.is_watchlist) {
        setWatchlist(prev => [...prev, symbol]);
        showToast(`Added ${symbol} to Watchlist`, 'success');
      } else {
        setWatchlist(prev => prev.filter(s => s !== symbol));
        showToast(`Removed ${symbol} from Watchlist`, 'info');
      }
    } catch (err) {
      console.error(err);
    }
  };

  // WebSocket Connection & Smart Polling
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    if (!isMasterFeedActive) {
      setMarketStatus({ label: '⏸ Feed Paused (API Offline)', color: 'text-slate-400', status: 'PAUSED' });
      setIsLiveWsConnected(false);
      return; // Do nothing else, no WS, no polling
    }

    const connectWs = () => {
      try {
        ws = new WebSocket(WS_URL);
        ws.onopen = () => {
          setIsLiveWsConnected(true);
        };
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'TICK_UPDATE') {
              setLastTick(msg);
              if (msg.quotes) {
                setLiveQuotes(prev => ({ ...prev, ...msg.quotes }));
              }
              // Always apply tick update using functional form to avoid stale closure
              if (msg.nifty50) {
                setOverview(prev => prev ? ({
                  ...prev,
                  nifty50: msg.nifty50,
                  banknifty: msg.banknifty ?? prev.banknifty,
                  ...(msg.market_breadth && { market_breadth: msg.market_breadth }),
                  ...(msg.active_signals_count != null && {
                    active_candidates: msg.active_signals_count
                  })
                }) : prev);
              }
            } else if (msg.type === 'NEW_ALERT') {
              setAlerts(prev => [msg.alert, ...prev]);
              setUnreadAlertsCount(prev => prev + 1);
              showToast(msg.alert.title, msg.alert.severity === 'SUCCESS' ? 'success' : 'info');
            }
          } catch (e) {}
        };
        ws.onclose = () => {
          setIsLiveWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 4000);
        };
        ws.onerror = () => {
          setIsLiveWsConnected(false);
        };
      } catch (err) {
        reconnectTimeout = setTimeout(connectWs, 4000);
      }
    };

    connectWs();
    refreshOverview();
    refreshAlerts();
    refreshPaperPortfolio();

    // ── SMART MARKET-HOURS POLLING ─────────────────────────────────────────
    // Only hammer the API during live market hours (09:15–15:30 IST Mon–Fri)
    // Outside hours: slow down dramatically to save Angel One API quota
    const startSmartPolling = () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);

      const mktOpen = isMarketOpen();
      const prePost = isPreMarket() || isPostMarket();
      let pollMs;
      if (mktOpen)        pollMs = 4000;         // Live market: 4s (need live prices)
      else if (prePost)   pollMs = 30000;        // Pre/post: 30s (slow check)
      else                pollMs = 5 * 60000;    // Night/weekend: 5 min (just keep warm)

      setMarketStatus(getMarketStatusLabel());

      pollingIntervalRef.current = setInterval(() => {
        // Re-evaluate interval every tick in case market just opened/closed
        const nowOpen = isMarketOpen();
        const nowPrePost = isPreMarket() || isPostMarket();
        const newMs = nowOpen ? 4000 : nowPrePost ? 30000 : 5 * 60000;
        if (newMs !== pollMs) {
          // Market status changed — restart with new interval
          startSmartPolling();
          return;
        }
        setMarketStatus(getMarketStatusLabel());
        refreshOverview();
        refreshAlerts();
        refreshPaperPortfolio();
      }, pollMs);
    };

    startSmartPolling();
    // Check every minute if market status changed (open → closed or vice versa)
    const statusCheckInterval = setInterval(() => {
      const currentStatus = getMarketStatus();
      if (currentStatus === 'CLOSED' && isMasterFeedActive) {
        // Auto-pause feed when market fully closes
        setIsMasterFeedActive(false);
        localStorage.setItem('trade_intel_master_feed', 'false');
        showToast('⏸ Auto-Paused Live Feed (Market Closed)', 'info');
      } else if (currentStatus === 'OPEN' && !isMasterFeedActive) {
        setIsMasterFeedActive(true);
        localStorage.setItem('trade_intel_master_feed', 'true');
        showToast('▶️ Market Open — Auto-Started Live Feed', 'success');
      } else {
        setMarketStatus(getMarketStatusLabel());
      }
    }, 60000);

    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      clearInterval(statusCheckInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [refreshOverview, refreshAlerts, refreshPaperPortfolio, isMasterFeedActive]);

  return (
    <MarketContext.Provider
      value={{
        overview,
        alerts,
        unreadAlertsCount,
        selectedSymbol,
        setSelectedSymbol,
        watchlist,
        toggleWatchlistSymbol,
        isLiveWsConnected,
        activeTab,
        setActiveTab,
        isAlertDrawerOpen,
        setIsAlertDrawerOpen,
        isPaperDrawerOpen,
        setIsPaperDrawerOpen,
        handleDismissAlert,
        refreshOverview,
        refreshAlerts,
        refreshPaperPortfolio,
        paperPortfolio,
        uiMode,
        toggleUiMode,
        isAudioMuted,
        toggleAudio,
        isMasterFeedActive,
        toggleMasterFeed,
        lastTick,
        liveQuotes,
        showToast,
        toast,
        marketStatus
      }}
    >
      {children}
    </MarketContext.Provider>
  );
};

export const useMarket = () => useContext(MarketContext);
