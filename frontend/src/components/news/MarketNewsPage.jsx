import React, { useState, useEffect } from 'react';
import { Newspaper, Search, Tag, ExternalLink, Sparkles, AlertCircle, TrendingUp, TrendingDown } from 'lucide-react';
import { fetchNews } from '../../services/api';
import { useMarket } from '../../context/MarketContext';

export default function MarketNewsPage() {
  const { setSelectedSymbol, setActiveTab } = useMarket();
  const [news, setNews] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedSentiment, setSelectedSentiment] = useState('');

  useEffect(() => {
    const loadNews = async () => {
      setIsLoading(true);
      try {
        const data = await fetchNews();
        setNews(data);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    loadNews();
  }, []);

  const handleInspectSymbol = (sym) => {
    setSelectedSymbol(sym);
    setActiveTab('analysis');
  };

  const filteredNews = news.filter(n => {
    if (selectedCategory && n.category !== selectedCategory) return false;
    if (selectedSentiment && n.sentiment !== selectedSentiment) return false;
    return true;
  });

  const getSentimentBadge = (sentiment, score) => {
    switch (sentiment) {
      case 'POSITIVE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 font-mono">
            <TrendingUp className="w-3 h-3" /> POSITIVE (+{(score * 100).toFixed(0)}%)
          </span>
        );
      case 'NEGATIVE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1 font-mono">
            <TrendingDown className="w-3 h-3" /> NEGATIVE ({(score * 100).toFixed(0)}%)
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700 font-mono">
            NEUTRAL
          </span>
        );
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-cyan-400" />
          Indian Market News & Event Intelligence
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Real-time financial disclosures, macro policy bulletins, and NLP sentiment classification.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 p-3.5 rounded-xl bg-slate-900/70 border border-slate-800 text-xs">
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-300 focus:outline-none"
        >
          <option value="">All Event Categories</option>
          <option value="EARNINGS">Earnings</option>
          <option value="POLICY">Policy / Regulatory</option>
          <option value="CORPORATE_ACTION">Corporate Action / Deals</option>
          <option value="MACRO">Macro Economics</option>
          <option value="GENERAL">General Industry</option>
        </select>

        <select
          value={selectedSentiment}
          onChange={(e) => setSelectedSentiment(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-300 focus:outline-none"
        >
          <option value="">All Sentiments</option>
          <option value="POSITIVE">Positive</option>
          <option value="NEGATIVE">Negative</option>
          <option value="NEUTRAL">Neutral</option>
        </select>

        <span className="text-slate-500 text-[11px] ml-auto font-mono">
          Showing {filteredNews.length} Intelligence Items
        </span>
      </div>

      {/* News Feed */}
      <div className="space-y-4">
        {filteredNews.map((item) => (
          <div
            key={item.news_id}
            className="p-5 rounded-xl bg-slate-900/80 border border-slate-800/80 hover:border-slate-700 transition-all hover:shadow-lg space-y-3"
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
              <div className="flex items-center space-x-2.5">
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-950 text-cyan-400 border border-slate-800">
                  {item.source}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {(() => {
                    try {
                      let s = String(item.timestamp || '').trim();
                      if (!s.endsWith('Z') && !s.includes('+') && !/[-+]\d{2}:\d{2}$/.test(s)) s = s.replace(' ', 'T') + 'Z';
                      const d = new Date(s);
                      return isNaN(d.getTime()) ? item.timestamp : d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true }) + ' IST';
                    } catch {
                      return item.timestamp;
                    }
                  })()}
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                  {item.category}
                </span>
              </div>

              {getSentimentBadge(item.sentiment, item.sentiment_score)}
            </div>

            <h3 className="text-sm font-bold text-white leading-snug">
              {item.headline}
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              {item.summary}
            </p>

            {/* Affected Tickers & Sectors */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/60 text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-[11px] text-slate-400 font-semibold">Impacted Tickers:</span>
                <div className="flex flex-wrap gap-1.5">
                  {item.affected_symbols.map((sym) => (
                    <button
                      key={sym}
                      onClick={() => handleInspectSymbol(sym)}
                      className="px-2 py-0.5 rounded bg-cyan-950/60 hover:bg-cyan-800/80 text-cyan-300 border border-cyan-800/60 text-[10.5px] font-mono font-bold transition-colors flex items-center gap-1"
                    >
                      <span>{sym}</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                <span>Sector:</span>
                <span className="font-semibold text-slate-300">{item.affected_sectors.join(', ')}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
