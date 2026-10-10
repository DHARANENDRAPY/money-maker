import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Key,
  ShieldCheck,
  Radio,
  CheckCircle2,
  AlertTriangle,
  Save,
  Lock,
  Plus,
  Trash2,
  Sliders,
  ExternalLink,
  ChevronRight,
  Info,
  Zap,
  Eye,
  EyeOff,
  RefreshCw,
  Wifi,
  WifiOff,
  BookOpen,
  Circle,
  ArrowRight,
  Send,
  MessageSquare,
  Bell
} from 'lucide-react';
import { fetchSettings, updateProviderSettings, fetchTelegramStatus, updateTelegramConfig, sendTestTelegramAlert } from '../../services/api';
import { useMarket } from '../../context/MarketContext';

const SETUP_STEPS = [
  {
    step: 1,
    title: 'Create an Angel One Account',
    desc: 'If you don\'t have one, open a free Demat account at angelone.in',
    link: 'https://www.angelone.in/',
    linkText: 'Open Angel One Account'
  },
  {
    step: 2,
    title: 'Log in to Angel One SmartAPI Portal',
    desc: 'Go to the SmartAPI developer portal and register as a developer',
    link: 'https://smartapi.angelbroking.com/',
    linkText: 'SmartAPI Developer Portal'
  },
  {
    step: 3,
    title: 'Create a New App to Get Your API Key',
    desc: 'Click "Create App" → fill in app details → your API Key (not login password) will be shown.',
  },
  {
    step: 4,
    title: 'Enable TOTP (Google Authenticator)',
    desc: 'In Angel One mobile app → Profile → My Profile → Enable TOTP. Scan the QR code with Google Authenticator. Save the 16-32 character Base32 secret key shown.',
  },
  {
    step: 5,
    title: 'Enter Credentials Below',
    desc: 'Fill in your SmartAPI Key, Client Code (Login ID), Account PIN, and TOTP Secret below, then click Connect.',
  }
];

export default function SettingsPage() {
  const { watchlist, toggleWatchlistSymbol, showToast, refreshOverview } = useMarket();
  const [provider, setProvider] = useState('demo');
  const [apiKey, setApiKey] = useState('');
  const [clientCode, setClientCode] = useState('');
  const [pin, setPin] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [newSymbol, setNewSymbol] = useState('');
  const [statusMsg, setStatusMsg] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [showTotp, setShowTotp] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Telegram Notifications State
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramChatId, setTelegramChatId] = useState('');
  const [telegramEnabled, setTelegramEnabled] = useState(true);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [isSavingTelegram, setIsSavingTelegram] = useState(false);
  const [isTestingTelegram, setIsTestingTelegram] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const [data, tg] = await Promise.all([
          fetchSettings(),
          fetchTelegramStatus().catch(() => null)
        ]);
        setProvider(data.active_provider || 'demo');
        setClientCode(data.angel_client_code || '');
        setIsAuthenticated(data.angel_authenticated || false);
        if (tg) {
          setTelegramStatus(tg);
          setTelegramEnabled(tg.enabled ?? true);
          if (tg.chat_id) setTelegramChatId(tg.chat_id);
        }
      } catch (err) {
        console.error(err);
      }
    };
    loadConfig();
  }, []);

  const handleSaveTelegram = async (e) => {
    e.preventDefault();
    if (!telegramToken.trim() && !telegramStatus?.has_token) {
      showToast('⚠️ Please enter your Telegram Bot Token', 'warning');
      return;
    }
    if (!telegramChatId.trim()) {
      showToast('⚠️ Please enter your Telegram Chat ID', 'warning');
      return;
    }
    setIsSavingTelegram(true);
    try {
      const res = await updateTelegramConfig({
        bot_token: telegramToken.trim(),
        chat_id: telegramChatId.trim(),
        enabled: telegramEnabled
      });
      if (res.success) {
        setTelegramStatus(res.status);
        showToast('✅ Telegram notification settings saved!', 'success');
      }
    } catch (err) {
      showToast('Failed to save Telegram settings: ' + err.message, 'error');
    } finally {
      setIsSavingTelegram(false);
    }
  };

  const handleTestTelegram = async () => {
    setIsTestingTelegram(true);
    try {
      const res = await sendTestTelegramAlert();
      if (res.success) {
        showToast('🔔 Test alert sent to Telegram! Check your phone.', 'success');
      } else {
        showToast(`Telegram Error: ${res.error || 'Failed to send alert'}`, 'error');
      }
    } catch (err) {
      showToast('Network error testing Telegram: ' + err.message, 'error');
    } finally {
      setIsTestingTelegram(false);
    }
  };

  const handleSaveProvider = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMsg(null);
    try {
      const res = await updateProviderSettings({
        data_provider: provider,
        angel_api_key: apiKey,
        angel_client_code: clientCode,
        angel_pin: pin,
        angel_totp_secret: totpSecret
      });
      if (res.success) {
        setStatusMsg({ type: 'success', text: res.message || 'Provider configuration saved successfully.' });
        setIsAuthenticated(true);
        showToast('✅ Angel One live feed connected!', 'success');
        refreshOverview();
      } else {
        setStatusMsg({ type: 'error', text: res.error || 'Connection failed. Please verify your credentials.' });
        setIsAuthenticated(false);
        showToast(res.error || 'Authentication failed', 'error');
      }
    } catch (err) {
      setStatusMsg({ type: 'error', text: 'Network error. Make sure the backend server is running on port 8000.' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSwitchToDemo = async () => {
    setIsSaving(true);
    try {
      const res = await updateProviderSettings({ data_provider: 'demo' });
      if (res.success) {
        setProvider('demo');
        setIsAuthenticated(false);
        showToast('Switched to Demo Simulation mode', 'info');
        refreshOverview();
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddWatchlist = (e) => {
    e.preventDefault();
    if (!newSymbol.trim()) return;
    toggleWatchlistSymbol(newSymbol.trim().toUpperCase());
    setNewSymbol('');
  };

  const FieldInput = ({ label, value, onChange, type = 'text', placeholder, showToggle, isShown, onToggle }) => (
    <div>
      <label className="text-[11px] text-slate-400 block mb-1 font-medium uppercase tracking-wider">{label}</label>
      <div className="relative">
        <input
          type={showToggle ? (isShown ? 'text' : 'password') : type}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-white font-mono text-sm focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/20 transition-all pr-10"
        />
        {showToggle && (
          <button
            type="button"
            onClick={onToggle}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
          >
            {isShown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-cyan-400" />
            Settings & Data Connectivity
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Configure your live market data provider, API credentials, and stock universe.
          </p>
        </div>
      </div>

      {/* Provider Mode Selector */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Market Data Feed</h2>
          </div>
          <div className={`flex items-center gap-2 text-[11px] font-mono px-3 py-1 rounded-full border ${
            provider === 'angel_one' && isAuthenticated
              ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300'
              : 'bg-slate-950 border-slate-700 text-slate-400'
          }`}>
            {provider === 'angel_one' && isAuthenticated
              ? <><Wifi className="w-3 h-3" /> LIVE FEED</>
              : <><WifiOff className="w-3 h-3" /> DEMO MODE</>
            }
          </div>
        </div>

        {/* Mode Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div
            onClick={() => setProvider('demo')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              provider === 'demo'
                ? 'bg-cyan-950/30 border-cyan-500/50 shadow-md shadow-cyan-500/5'
                : 'bg-slate-950/60 border-slate-700 hover:border-slate-600'
            }`}
          >
            <div className="flex items-center space-x-2 mb-2">
              <input type="radio" checked={provider === 'demo'} onChange={() => setProvider('demo')} className="text-cyan-500 accent-cyan-500" />
              <span className="text-xs font-bold text-white">Demo Simulation</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">FREE</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              High-fidelity synthetic NSE intraday simulation. All features work — signals, factors, risk calculator, journal. No API key needed.
            </p>
            {provider === 'demo' && (
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-cyan-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" /> Currently Active
              </div>
            )}
          </div>

          <div
            onClick={() => setProvider('angel_one')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              provider === 'angel_one'
                ? 'bg-cyan-950/30 border-cyan-500/50 shadow-md shadow-cyan-500/5'
                : 'bg-slate-950/60 border-slate-700 hover:border-slate-600'
            }`}
          >
            <div className="flex items-center space-x-2 mb-2">
              <input type="radio" checked={provider === 'angel_one'} onChange={() => setProvider('angel_one')} className="text-cyan-500 accent-cyan-500" />
              <span className="text-xs font-bold text-white">Angel One SmartAPI</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/60 text-emerald-400 font-mono border border-emerald-800/50">LIVE</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Connects to your real Angel One brokerage account for live NSE tick data, LTP quotes, and historical candles.
            </p>
            {provider === 'angel_one' && isAuthenticated && (
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" /> Live session active for {clientCode}
              </div>
            )}
          </div>
        </div>

        {/* Quick Switch to Demo */}
        {provider === 'angel_one' && isAuthenticated && (
          <div className="flex justify-end">
            <button
              onClick={handleSwitchToDemo}
              disabled={isSaving}
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Switch back to Demo
            </button>
          </div>
        )}

        {/* Angel One Credentials Form */}
        {provider === 'angel_one' && (
          <form onSubmit={handleSaveProvider} className="space-y-5 pt-3 border-t border-slate-800">
            {/* Step-by-step Guide Toggle */}
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-white flex items-center gap-2">
                <Key className="w-4 h-4 text-cyan-400" />
                SmartAPI Credentials
              </h3>
              <button
                type="button"
                onClick={() => setShowGuide(g => !g)}
                className="flex items-center gap-1.5 text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
              >
                <BookOpen className="w-3.5 h-3.5" />
                {showGuide ? 'Hide Setup Guide' : 'How to Get Credentials?'}
              </button>
            </div>

            {/* Setup Guide */}
            {showGuide && (
              <div className="rounded-xl border border-cyan-800/40 bg-cyan-950/20 p-4 space-y-3">
                <div className="text-[11px] font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                  <Zap className="w-3.5 h-3.5" />
                  Step-by-Step: Get Your Angel One API Key
                </div>
                {SETUP_STEPS.map((s) => (
                  <div key={s.step} className="flex gap-3">
                    <div className="shrink-0 w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 text-[10px] font-bold flex items-center justify-center border border-cyan-500/30">
                      {s.step}
                    </div>
                    <div>
                      <div className="text-[11px] font-bold text-white">{s.title}</div>
                      <div className="text-[11px] text-slate-400 leading-relaxed">{s.desc}</div>
                      {s.link && (
                        <a
                          href={s.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 mt-0.5 transition-colors"
                        >
                          {s.linkText}
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
                <div className="mt-3 p-3 rounded-lg bg-amber-950/40 border border-amber-800/40 text-[11px] text-amber-300 flex gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>
                    <strong>TOTP Secret ≠ 6-digit code.</strong> The TOTP Secret is the long 16–32 character Base32 string (e.g. JBSWY3DPEHPK3PXP) shown when you scan the QR code. Do NOT enter the temporary 6-digit OTP.
                  </span>
                </div>
              </div>
            )}

            {/* Fields */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldInput
                label="SmartAPI Key"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="e.g. aB3xK9..."
              />
              <FieldInput
                label="Client Code (Login ID)"
                value={clientCode}
                onChange={e => setClientCode(e.target.value)}
                placeholder="e.g. A123456"
              />
              <FieldInput
                label="Account PIN / MPIN"
                value={pin}
                onChange={e => setPin(e.target.value)}
                showToggle={true}
                isShown={showPin}
                onToggle={() => setShowPin(v => !v)}
                placeholder="4–6 digit PIN"
              />
              <FieldInput
                label="TOTP Secret (Base32)"
                value={totpSecret}
                onChange={e => setTotpSecret(e.target.value)}
                showToggle={true}
                isShown={showTotp}
                onToggle={() => setShowTotp(v => !v)}
                placeholder="16–32 char secret, e.g. JBSWY3DP..."
              />
            </div>

            {/* Status Message */}
            {statusMsg && (
              <div className={`p-3.5 rounded-xl border flex items-start gap-2.5 text-xs ${
                statusMsg.type === 'success'
                  ? 'bg-emerald-950/40 border-emerald-700/60 text-emerald-300'
                  : 'bg-rose-950/40 border-rose-700/60 text-rose-300'
              }`}>
                {statusMsg.type === 'success'
                  ? <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  : <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                }
                <span>{statusMsg.text}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
              <div className="flex items-center space-x-1.5 text-[11px] text-slate-400">
                <Lock className="w-3.5 h-3.5 text-slate-500" />
                <span>Credentials stored in server session memory only. Never transmitted externally.</span>
              </div>
              <button
                type="submit"
                disabled={isSaving}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs flex items-center gap-2 transition-all shadow-lg shadow-cyan-600/20 disabled:opacity-60 shrink-0"
              >
                {isSaving ? (
                  <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Connecting...</>
                ) : (
                  <><Zap className="w-3.5 h-3.5" /> Connect & Authenticate</>
                )}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Telegram Notifications Card */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center">
              <Send className="w-4 h-4 text-sky-400" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                Telegram Instant Trade Alerts
              </h2>
              <p className="text-[11px] text-slate-400">Receive AI trade recommendations & entry/exit plans on your phone</p>
            </div>
          </div>
          <div className={`flex items-center gap-1.5 text-[11px] font-mono px-3 py-1 rounded-full border ${
            telegramStatus?.enabled
              ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300'
              : 'bg-slate-950 border-slate-700 text-slate-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${telegramStatus?.enabled ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            {telegramStatus?.enabled ? 'ALERTS ACTIVE' : 'NOT CONFIGURED'}
          </div>
        </div>

        {/* Telegram Form */}
        <form onSubmit={handleSaveTelegram} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-[11px] text-slate-400 block mb-1 font-medium uppercase tracking-wider">
                Telegram Bot Token
              </label>
              <input
                type="password"
                placeholder={telegramStatus?.has_token ? '•••••••••••••••••••• (Configured)' : 'e.g. 123456789:ABCdefGhI...'}
                value={telegramToken}
                onChange={e => setTelegramToken(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] text-slate-400 block mb-1 font-medium uppercase tracking-wider">
                Telegram Chat ID / User ID
              </label>
              <input
                type="text"
                placeholder="e.g. 987654321"
                value={telegramChatId}
                onChange={e => setTelegramChatId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2.5 text-white font-mono text-xs focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 transition-all"
              />
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 select-none">
              <input
                type="checkbox"
                checked={telegramEnabled}
                onChange={e => setTelegramEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-950 text-sky-500 focus:ring-0 cursor-pointer"
              />
              <span>Enable automatic Telegram notifications for new high-conviction AI picks</span>
            </label>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleTestTelegram}
                disabled={isTestingTelegram || !telegramStatus?.has_token}
                className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-300 font-medium text-xs flex items-center gap-1.5 border border-slate-700 transition-colors disabled:opacity-40"
                title="Send a sample alert to verify connection"
              >
                <Bell className={`w-3.5 h-3.5 ${isTestingTelegram ? 'animate-spin' : ''}`} />
                {isTestingTelegram ? 'Sending...' : 'Send Test Alert'}
              </button>

              <button
                type="submit"
                disabled={isSavingTelegram}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs flex items-center gap-1.5 transition-all shadow-lg shadow-sky-600/20 disabled:opacity-60"
              >
                <Save className="w-3.5 h-3.5" />
                {isSavingTelegram ? 'Saving...' : 'Save Telegram Config'}
              </button>
            </div>
          </div>
        </form>

        {/* Quick Setup Guide */}
        <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-400 space-y-1.5">
          <div className="text-slate-300 font-semibold flex items-center gap-1.5 text-[11px]">
            <Info className="w-3.5 h-3.5 text-sky-400" />
            How to set up your free Telegram Bot in 60 seconds:
          </div>
          <ol className="list-decimal list-inside space-y-1 text-[11px] text-slate-400 pl-1">
            <li>Search <span className="text-sky-300 font-mono">@BotFather</span> on Telegram and send <span className="text-white font-mono">/newbot</span> to get your <strong>Bot Token</strong>.</li>
            <li>Search <span className="text-sky-300 font-mono">@userinfobot</span> on Telegram and click Start to get your <strong>Chat ID</strong>.</li>
            <li>Paste both above, click <strong>Save</strong>, then click <strong>Send Test Alert</strong> to verify!</li>
          </ol>
        </div>
      </div>

      {/* Watchlist Manager */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            Stock Watchlist ({watchlist.length} symbols)
          </h2>
          <span className="text-[11px] text-slate-400 font-mono">NSE Equity Universe</span>
        </div>

        <form onSubmit={handleAddWatchlist} className="flex gap-2">
          <input
            type="text"
            placeholder="Add NSE Symbol (e.g. BAJFINANCE)..."
            value={newSymbol}
            onChange={e => setNewSymbol(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-cyan-500 flex-1 max-w-xs"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-cyan-600 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Symbol
          </button>
        </form>

        <div className="flex flex-wrap gap-2 pt-1">
          {watchlist.map(sym => (
            <div
              key={sym}
              className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 flex items-center space-x-2 text-xs font-mono font-bold text-slate-200 hover:border-slate-700 transition-colors group"
            >
              <span>{sym}</span>
              <button
                onClick={() => toggleWatchlistSymbol(sym)}
                className="text-slate-600 group-hover:text-rose-400 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Risk Defaults Info Card */}
      <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-3">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
          <ShieldCheck className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-bold text-white uppercase tracking-wider">Platform Defaults</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          {[
            { label: 'Default Capital', value: '₹1,00,000' },
            { label: 'Risk Per Trade', value: '1.0%' },
            { label: 'Max Daily Loss', value: '3.0%' },
            { label: 'Slippage Est.', value: '5 bps' },
          ].map(item => (
            <div key={item.label} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
              <div className="text-[10px] text-slate-400 uppercase tracking-wider">{item.label}</div>
              <div className="font-mono font-bold text-white mt-1">{item.value}</div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
          <Info className="w-3.5 h-3.5 shrink-0" />
          These defaults are used in the Risk Calculator and Position Sizing. Individual trades can override these values.
        </p>
      </div>
    </div>
  );
}
