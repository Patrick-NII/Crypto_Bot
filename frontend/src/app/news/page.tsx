"use client";

import { useEffect, useState, useCallback } from "react";
import { usePageAccent, PAGE_ACCENTS } from "@/components/providers/theme-provider";
import {
  Newspaper,
  TrendingUp,
  RefreshCw,
  ExternalLink,
  Sparkles,
  Loader2,
  Flame,
  Filter,
  Search,
} from "lucide-react";
import { newsApi, binanceApi, pricesApi, aiApi } from "@/lib/api";
import type { NewsArticle, TrendingCoin, MarketSentiment } from "@/lib/types";
import { cn, formatRelative } from "@/lib/utils";

// ============================================================
// Constants
// ============================================================

const REFRESH_INTERVAL = 60_000;
const FEED_LIMIT = 30;
const AI_CACHE_KEY = "okamoey-news-digest";
const AI_CACHE_TTL = 900_000; // 15 min
const IMPACT_OPTIONS = ["all", "high", "medium", "low"] as const;

type ImpactFilter = (typeof IMPACT_OPTIONS)[number];

// ============================================================
// Helpers
// ============================================================

function sentimentColor(s: number) {
  if (s >= 0.3) return "text-[var(--success)]";
  if (s <= -0.3) return "text-[var(--danger)]";
  return "text-[var(--text-secondary)]";
}

function sentimentLabel(s: number) {
  if (s >= 0.3) return "Bullish";
  if (s <= -0.3) return "Bearish";
  return "Neutral";
}

function impactDot(impact: string) {
  if (impact === "high") return "bg-[var(--danger)]";
  if (impact === "medium") return "bg-[var(--warning)]";
  return "bg-[var(--text-muted)]";
}

function overallColor(o: string) {
  if (o === "bullish") return "text-[var(--success)]";
  if (o === "bearish") return "text-[var(--danger)]";
  return "text-[var(--text-secondary)]";
}

function readCache(key: string, ttl: number): string | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (Date.now() - p.ts < ttl) return p.text;
  } catch { /* ignore */ }
  return null;
}

function writeCache(key: string, text: string) {
  try { localStorage.setItem(key, JSON.stringify({ text, ts: Date.now() })); } catch { /* full */ }
}

// ============================================================
// News Page
// ============================================================

export default function NewsPage() {
  usePageAccent(PAGE_ACCENTS.news.accent, PAGE_ACCENTS.news.glow);

  const [loading, setLoading] = useState(true);
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [trending, setTrending] = useState<TrendingCoin[]>([]);
  const [sentiment, setSentiment] = useState<MarketSentiment | null>(null);
  const [holdingSymbols, setHoldingSymbols] = useState<string[]>([]);
  const [lastUpdate, setLastUpdate] = useState("");

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [impactFilter, setImpactFilter] = useState<ImpactFilter>("all");
  const [symbolFilter, setSymbolFilter] = useState<string>("");

  // AI Digest
  const [aiDigest, setAiDigest] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [feedRes, trendRes, sentRes, balRes] = await Promise.allSettled([
        newsApi.getFeed(FEED_LIMIT),
        newsApi.getTrending(),
        newsApi.getSentiment(),
        binanceApi.getBalances(),
      ]);

      if (feedRes.status === "fulfilled") setArticles(feedRes.value);
      if (trendRes.status === "fulfilled") setTrending(trendRes.value);
      if (sentRes.status === "fulfilled") setSentiment(sentRes.value);

      if (balRes.status === "fulfilled") {
        const STABLES = new Set(["USDT", "BUSD", "USDC", "USD", "FDUSD"]);
        const syms = balRes.value
          .filter((b) => b.free + b.locked > 0 && !STABLES.has(b.asset))
          .map((b) => b.asset);
        setHoldingSymbols(syms);
      }

      setLastUpdate(new Date().toLocaleTimeString());
    } catch { /* per-request */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchData();
    const i = setInterval(fetchData, REFRESH_INTERVAL);
    return () => clearInterval(i);
  }, [fetchData]);

  // AI Digest handler
  const handleAiDigest = useCallback(async () => {
    setAiLoading(true);
    try {
      const cached = readCache(AI_CACHE_KEY, AI_CACHE_TTL);
      if (cached) { setAiDigest(cached); setAiLoading(false); return; }

      const topArticles = articles.slice(0, 10).map((a) => ({
        title: a.title,
        sentiment: a.sentiment,
        impact: a.impact,
        source: a.source,
      }));
      const res = await aiApi.analyzePerformance({
        context: "news_digest",
        articles: topArticles,
        sentiment: sentiment ? { overall: sentiment.overall, fear_greed: sentiment.fear_greed.value, news_sentiment: sentiment.news_sentiment } : null,
        trending: trending.slice(0, 5).map((t) => t.symbol),
        user_holdings: holdingSymbols,
      });
      const text = res.analysis.slice(0, 1200);
      setAiDigest(text);
      writeCache(AI_CACHE_KEY, text);
    } catch {
      setAiDigest("IA indisponible. V\u00e9rifiez la configuration API.");
    } finally { setAiLoading(false); }
  }, [articles, sentiment, trending, holdingSymbols]);

  // Filtered articles
  const filtered = articles.filter((a) => {
    if (impactFilter !== "all" && a.impact !== impactFilter) return false;
    if (symbolFilter && !a.title.toLowerCase().includes(symbolFilter.toLowerCase()) && !a.categories.some((c) => c.toLowerCase().includes(symbolFilter.toLowerCase()))) return false;
    if (searchQuery && !a.title.toLowerCase().includes(searchQuery.toLowerCase()) && !a.body.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  // Portfolio-relevant articles
  const portfolioNews = holdingSymbols.length > 0
    ? articles.filter((a) => holdingSymbols.some((sym) => a.title.toUpperCase().includes(sym) || a.categories.some((c) => c.toUpperCase().includes(sym))))
    : [];

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl p-4 md:p-8">
        <div className="h-6 w-48 animate-pulse rounded-lg bg-white/5 mb-6" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 mb-6">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 animate-pulse rounded-xl bg-white/5" />)}</div>
        <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-white/5" />)}</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl p-4 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-bold glow-text">Market Intelligence</h1>
          <p className="text-[13px] text-[var(--text-muted)]">{articles.length} articles &middot; Auto-refresh 60s</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
          <RefreshCw className="h-3.5 w-3.5" />
          {lastUpdate && <span>{lastUpdate}</span>}
        </button>
      </div>

      {/* Sentiment Bar */}
      {sentiment && (
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4 mb-6">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">Fear & Greed</p>
            <p className="text-2xl font-bold font-mono text-[var(--foreground)]">{sentiment.fear_greed.value}</p>
            <p className="text-[12px] text-[var(--text-muted)]">{sentiment.fear_greed.label}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">News Sentiment</p>
            <p className={cn("text-2xl font-bold font-mono", sentimentColor(sentiment.news_sentiment))}>
              {sentiment.news_sentiment > 0 ? "+" : ""}{sentiment.news_sentiment.toFixed(2)}
            </p>
            <p className={cn("text-[12px]", sentimentColor(sentiment.news_sentiment))}>{sentimentLabel(sentiment.news_sentiment)}</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">Overall</p>
            <p className={cn("text-2xl font-bold capitalize", overallColor(sentiment.overall))}>{sentiment.overall}</p>
            <p className="text-[12px] text-[var(--text-muted)]">{sentiment.news_count} sources</p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] mb-1">Trending</p>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {trending.slice(0, 5).map((t) => (
                <span key={t.symbol} className="flex items-center gap-1 text-[12px] text-[var(--foreground)]">
                  {t.thumb && <img src={t.thumb} alt="" className="h-3.5 w-3.5 rounded-full" />}
                  {t.symbol}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters + Search */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex items-center gap-2 flex-1 min-w-[200px] rounded-xl px-3 py-2 border border-[var(--glass-border)]" style={{ background: "var(--glass-bg)" }}>
          <Search className="h-3.5 w-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher dans les news..."
            className="flex-1 bg-transparent text-[14px] text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]"
          />
        </div>
        <div className="flex items-center gap-1">
          <Filter className="h-3 w-3 text-[var(--text-muted)]" />
          {IMPACT_OPTIONS.map((opt) => (
            <button key={opt} onClick={() => setImpactFilter(opt)}
              className={cn("rounded-lg px-2.5 py-1 text-[12px] font-medium transition-all capitalize",
                impactFilter === opt ? "bg-[var(--page-accent)]/15 text-[var(--page-accent)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
              )}>
              {opt === "all" ? "Tout" : opt}
            </button>
          ))}
        </div>
        {holdingSymbols.length > 0 && (
          <button
            onClick={() => setSymbolFilter(symbolFilter ? "" : "portfolio")}
            className={cn("rounded-lg px-2.5 py-1 text-[12px] font-medium transition-all",
              symbolFilter ? "bg-[var(--page-accent)]/15 text-[var(--page-accent)]" : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            )}
          >
            Mon Portfolio
          </button>
        )}
      </div>

      {/* 2-column layout */}
      <div className="grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-7">

        {/* Left — News Feed (4/7) */}
        <div className="lg:col-span-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[var(--foreground)] flex items-center gap-1.5">
              <Newspaper className="h-3.5 w-3.5 accent-text" /> News Feed
            </h2>
            <span className="text-[12px] text-[var(--text-muted)]">{filtered.length} articles</span>
          </div>

          {filtered.length === 0 ? (
            <div className="py-16 text-center">
              <Newspaper className="h-8 w-8 mx-auto mb-3 text-[var(--text-muted)] opacity-30" />
              <p className="text-sm text-[var(--text-muted)]">{articles.length === 0 ? "Chargement des news..." : "Aucun r\u00e9sultat pour ces filtres"}</p>
            </div>
          ) : (
            <div className="space-y-1">
              {filtered.map((article) => (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex gap-4 px-2 py-3 rounded-lg hover:bg-[var(--glass-bg)] transition-all group cursor-pointer"
                >
                  {/* Image */}
                  {article.image && (
                    <img src={article.image} alt="" className="h-16 w-24 rounded-lg object-cover flex-shrink-0 opacity-80 group-hover:opacity-100 transition-opacity" />
                  )}

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-[15px] font-semibold text-[var(--foreground)] line-clamp-2 leading-snug group-hover:text-[var(--page-accent)] transition-colors">
                        {article.title}
                      </h3>
                      <ExternalLink className="h-3 w-3 flex-shrink-0 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity mt-0.5" />
                    </div>

                    <p className="text-[13px] text-[var(--text-muted)] line-clamp-1 mt-1">{article.body}</p>

                    <div className="flex items-center gap-3 mt-1.5">
                      <span className="text-[11px] text-[var(--text-muted)]">{article.source}</span>
                      <span className="text-[11px] text-[var(--text-muted)]">{formatRelative(article.published_at)}</span>
                      <span className={cn("h-1.5 w-1.5 rounded-full", impactDot(article.impact))} title={`Impact: ${article.impact}`} />
                      <span className={cn("text-[11px] font-medium", sentimentColor(article.sentiment))}>
                        {sentimentLabel(article.sentiment)}
                      </span>
                      {article.categories.slice(0, 2).map((cat) => (
                        <button key={cat} onClick={(e) => { e.preventDefault(); setSymbolFilter(cat); }}
                          className="text-[10px] rounded px-1.5 py-0.5 text-[var(--text-muted)] hover:text-[var(--page-accent)] transition-colors"
                          style={{ background: "var(--glass-bg)" }}>
                          {cat}
                        </button>
                      ))}
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* Right column (3/7) */}
        <div className="lg:col-span-3 space-y-8">

          {/* AI News Digest */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-[var(--foreground)] flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 accent-text" /> AI Digest
              </h2>
              <button onClick={handleAiDigest} disabled={aiLoading}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[13px] font-medium accent-text hover:bg-[var(--glass-bg)] transition-all disabled:opacity-40">
                {aiLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                {aiLoading ? "Analyse..." : "G\u00e9n\u00e9rer"}
              </button>
            </div>
            {aiDigest ? (
              <div className="relative">
                <div className="max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                  <div className="text-[15px] leading-[1.75] text-[var(--text-secondary)]">
                    {aiDigest.split("\n").map((line, i) => {
                      const trimmed = line.trim();
                      if (!trimmed) return <div key={i} className="h-3" />;
                      const isLabel = /^(SITUATION|DYNAMIQUE|OPPORTUNIT|CONSEIL|RISQUE|TENDANCE|IMPACT)/i.test(trimmed);
                      if (isLabel) {
                        const colonIdx = trimmed.indexOf(":");
                        const label = colonIdx > 0 ? trimmed.slice(0, colonIdx) : trimmed;
                        const body = colonIdx > 0 ? trimmed.slice(colonIdx + 1).trim() : "";
                        return (
                          <div key={i} className="mb-3">
                            <p className="text-[13px] font-bold uppercase tracking-[0.12em] accent-text mb-1">{label.trim()}</p>
                            {body && <p className="text-[15px] leading-[1.75] text-[var(--text-secondary)]">{body}</p>}
                          </div>
                        );
                      }
                      return <p key={i} className="mb-2">{trimmed}</p>;
                    })}
                  </div>
                </div>
                <div className="pointer-events-none absolute bottom-0 left-0 right-2 h-6 bg-gradient-to-t from-[var(--bg)] to-transparent" />
              </div>
            ) : (
              <p className="text-[14px] text-[var(--text-muted)] leading-relaxed">
                R&eacute;sum&eacute; IA des news cl&eacute;s : tendances, impacts sur votre portfolio et recommandations.
              </p>
            )}
          </div>

          {/* Trending coins */}
          {trending.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3 flex items-center gap-1.5">
                <Flame className="h-3.5 w-3.5 accent-text" /> Trending
              </h2>
              <div className="space-y-2">
                {trending.slice(0, 8).map((coin, i) => (
                  <div key={coin.symbol} className="flex items-center justify-between py-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[12px] text-[var(--text-muted)] w-4">{i + 1}</span>
                      {coin.thumb && <img src={coin.thumb} alt="" className="h-5 w-5 rounded-full" />}
                      <div>
                        <p className="text-[13px] font-semibold text-[var(--foreground)]">{coin.symbol}</p>
                        <p className="text-[11px] text-[var(--text-muted)]">{coin.name}</p>
                      </div>
                    </div>
                    <span className="text-[11px] font-mono text-[var(--text-muted)]">Score {coin.score}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Portfolio-relevant news */}
          {portfolioNews.length > 0 && (
            <div>
              <h2 className="text-xs font-semibold text-[var(--foreground)] mb-3 flex items-center gap-1.5">
                <TrendingUp className="h-3.5 w-3.5 accent-text" /> News Portfolio
              </h2>
              <div className="space-y-2">
                {portfolioNews.slice(0, 5).map((article) => (
                  <a key={article.id} href={article.url} target="_blank" rel="noopener noreferrer"
                    className="block py-2 hover:bg-[var(--glass-bg)] rounded-lg px-2 transition-all">
                    <p className="text-[13px] font-semibold text-[var(--foreground)] line-clamp-2 leading-snug">{article.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[11px] text-[var(--text-muted)]">{article.source}</span>
                      <span className={cn("h-1.5 w-1.5 rounded-full", impactDot(article.impact))} />
                      <span className={cn("text-[11px] font-medium", sentimentColor(article.sentiment))}>{sentimentLabel(article.sentiment)}</span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
