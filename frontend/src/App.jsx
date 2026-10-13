import React, { Component } from 'react';
import { MarketProvider, useMarket } from './context/MarketContext';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import StatusBanner from './components/layout/StatusBanner';
import MobileNav from './components/layout/MobileNav';
import AlertDrawer from './components/alerts/AlertDrawer';

import RecommendationsPage from './components/recommendations/RecommendationsPage';
import DeliveryPage from './components/delivery/DeliveryPage';
import PaperTradingPage from './components/paper/PaperTradingPage';
import HistoryPage from './components/history/HistoryPage';
import SettingsPage from './components/settings/SettingsPage';
import PaperTradingDrawer from './components/paper/PaperTradingDrawer';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center text-slate-300">
          <div className="bg-rose-500/10 border border-rose-500/30 p-6 rounded-2xl max-w-lg shadow-xl shadow-rose-500/5">
            <h2 className="text-xl font-bold text-rose-400 mb-2">Something went wrong</h2>
            <p className="text-sm text-slate-400 mb-6">A component crashed while rendering. This section has been isolated to prevent the entire dashboard from breaking.</p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function DashboardContent() {
  const { activeTab, toast } = useMarket();

  const renderActivePage = () => {
    switch (activeTab) {
      case 'recommendations':
        return <RecommendationsPage />;
      case 'delivery':
        return <DeliveryPage />;
      case 'paper':
        return <PaperTradingPage />;
      case 'history':
        return <HistoryPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <RecommendationsPage />;
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 antialiased font-sans">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Terminal Viewport */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <StatusBanner />
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <ErrorBoundary>
            {renderActivePage()}
          </ErrorBoundary>
        </main>
      </div>

      {/* Mobile Navigation */}
      <MobileNav />

      {/* Slide-out Alert Drawer */}
      <AlertDrawer />

      {/* Slide-out Paper Trading Portfolio Drawer */}
      <PaperTradingDrawer />

      {/* Global Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 p-4 rounded-xl bg-slate-900 border border-cyan-500/40 text-xs text-white shadow-2xl animate-fade-in flex items-center space-x-2 font-medium">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          <span>{toast.message}</span>
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <MarketProvider>
      <DashboardContent />
    </MarketProvider>
  );
}
