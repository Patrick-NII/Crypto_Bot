"use client";

import Link from "next/link";
import {
  Bot,
  BarChart3,
  Shield,
  Zap,
  TrendingUp,
  Bell,
  ChevronDown,
  Check,
  ArrowRight,
} from "lucide-react";
import { useState } from "react";

const FEATURES = [
  {
    icon: Bot,
    title: "AI Trading Agents",
    desc: "6 specialized AI agents that analyze your portfolio, execute trades, and optimize strategies using GPT-4o and Claude.",
  },
  {
    icon: BarChart3,
    title: "Real-Time Analytics",
    desc: "Professional-grade charts, equity curves, and risk metrics updated in real-time via WebSocket.",
  },
  {
    icon: Shield,
    title: "Risk Management",
    desc: "Automated stop-losses, VaR calculations, portfolio drawdown alerts, and position sizing.",
  },
  {
    icon: Zap,
    title: "Paper Trading",
    desc: "Test strategies risk-free with realistic paper trading before committing real capital.",
  },
  {
    icon: TrendingUp,
    title: "Strategy Builder",
    desc: "Describe strategies in plain English. Our AI translates them into executable trading algorithms.",
  },
  {
    icon: Bell,
    title: "Smart Alerts",
    desc: "Price alerts, pattern detection, and portfolio risk notifications via email, push, or SMS.",
  },
];

const PLANS = [
  {
    name: "Free",
    price: "0",
    period: "forever",
    features: ["1 Portfolio", "Paper trading only", "Basic analytics", "5 AI queries/day", "Email alerts"],
    cta: "Get Started",
    highlight: false,
  },
  {
    name: "Pro",
    price: "49",
    period: "/month",
    features: ["Unlimited portfolios", "Live + paper trading", "Full analytics suite", "Unlimited AI queries", "All alert channels", "Strategy backtesting", "Priority support"],
    cta: "Start Free Trial",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "199",
    period: "/month",
    features: ["Everything in Pro", "Multi-exchange support", "Custom AI agents", "API access", "Dedicated account manager", "White-label option", "SLA guarantee"],
    cta: "Contact Sales",
    highlight: false,
  },
];

const FAQ = [
  { q: "Is my money safe?", a: "Okamoey never holds your funds. We connect to exchanges via read-only API keys for analytics, and trade-enabled keys only when you explicitly allow it." },
  { q: "Which exchanges are supported?", a: "We currently support Binance, Coinbase Pro, and Kraken. More exchanges are added regularly." },
  { q: "How do the AI agents work?", a: "Each page has a specialized AI agent that uses live data from your portfolio and market feeds. Simple questions use GPT-4o-mini, complex analysis uses Claude." },
  { q: "Can I cancel anytime?", a: "Yes, all subscriptions are month-to-month with no long-term commitment. Cancel anytime from your account settings." },
];

export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen bg-[#0d0d12]">
      {/* Nav */}
      <nav className="fixed top-0 z-50 w-full border-b border-[rgba(255,255,255,0.06)] bg-[#0d0d12]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="text-xl font-bold glow-text">OKAMOEY</span>
          <div className="hidden items-center gap-8 md:flex">
            <a href="#features" className="text-sm text-[#8888a0] hover:text-white">Features</a>
            <a href="#pricing" className="text-sm text-[#8888a0] hover:text-white">Pricing</a>
            <a href="#faq" className="text-sm text-[#8888a0] hover:text-white">FAQ</a>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="rounded-lg px-4 py-2 text-sm text-[#8888a0] hover:text-white">Log in</Link>
            <Link href="/register" className="rounded-lg bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] px-4 py-2 text-sm font-semibold text-[#0d0d12] hover:scale-105 transition-transform">Start Trading</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 pt-20">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.08)_0%,transparent_60%)]" />
        <div className="relative z-10 mx-auto max-w-4xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#06d6a0]/20 bg-[#06d6a0]/10 px-4 py-1.5">
            <Zap className="h-3.5 w-3.5 text-[#06d6a0]" />
            <span className="text-xs font-medium text-[#06d6a0]">AI-Powered Trading Platform</span>
          </div>
          <h1 className="mb-6 text-5xl font-bold leading-tight text-white md:text-7xl">
            Trade Smarter with{" "}
            <span className="bg-gradient-to-r from-[#06d6a0] to-[#c6f135] bg-clip-text text-transparent">AI Agents</span>
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-lg text-[#8888a0] md:text-xl">
            Okamoey combines real-time market data, professional analytics, and intelligent AI agents to help you build, test, and execute winning trading strategies.
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/register" className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] px-8 py-3.5 text-base font-semibold text-[#0d0d12] hover:scale-105 transition-transform">
              Start Free <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#features" className="rounded-xl border border-[rgba(255,255,255,0.08)] px-8 py-3.5 text-base text-[#8888a0] hover:border-[rgba(255,255,255,0.15)] hover:text-white">See Features</a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold text-white md:text-4xl">Everything you need to trade</h2>
            <p className="text-[#8888a0]">Professional-grade tools powered by artificial intelligence</p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="group rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-6 transition-all hover:border-[#06d6a0]/20 hover:shadow-lg hover:shadow-[#06d6a0]/5">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#06d6a0]/10">
                  <f.icon className="h-6 w-6 text-[#06d6a0]" />
                </div>
                <h3 className="mb-2 text-lg font-semibold text-white">{f.title}</h3>
                <p className="text-sm leading-relaxed text-[#8888a0]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="relative px-6 py-24">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(198,241,53,0.05)_0%,transparent_60%)]" />
        <div className="relative mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold text-white md:text-4xl">Simple, transparent pricing</h2>
            <p className="text-[#8888a0]">Start free, upgrade when you&apos;re ready</p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {PLANS.map((plan) => (
              <div key={plan.name} className={`relative rounded-2xl border p-8 ${plan.highlight ? "border-[#06d6a0]/40 bg-[#14141b] shadow-lg shadow-[#06d6a0]/10" : "border-[rgba(255,255,255,0.06)] bg-[#14141b]"}`}>
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-[#06d6a0] to-[#c6f135] px-4 py-1 text-xs font-bold text-[#0d0d12]">Most Popular</div>
                )}
                <h3 className="mb-2 text-lg font-semibold text-white">{plan.name}</h3>
                <div className="mb-6 flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-white">${plan.price}</span>
                  <span className="text-[#55556a]">{plan.period}</span>
                </div>
                <ul className="mb-8 space-y-3">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-center gap-2 text-sm text-[#8888a0]">
                      <Check className="h-4 w-4 flex-shrink-0 text-[#06d6a0]" />
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link href={plan.name === "Enterprise" ? "#" : "/register"} className={`block w-full rounded-xl py-3 text-center text-sm font-semibold ${plan.highlight ? "bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] text-[#0d0d12]" : "border border-[rgba(255,255,255,0.08)] text-white hover:border-[rgba(255,255,255,0.15)]"}`}>
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="px-6 py-24">
        <div className="mx-auto max-w-3xl">
          <h2 className="mb-12 text-center text-3xl font-bold text-white md:text-4xl">Frequently asked questions</h2>
          <div className="space-y-3">
            {FAQ.map((item, i) => (
              <div key={i} className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#14141b]">
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="flex w-full items-center justify-between p-5 text-left">
                  <span className="text-sm font-medium text-white">{item.q}</span>
                  <ChevronDown className={`h-4 w-4 text-[#55556a] transition-transform ${openFaq === i ? "rotate-180" : ""}`} />
                </button>
                {openFaq === i && (
                  <div className="border-t border-[rgba(255,255,255,0.06)] px-5 pb-5 pt-3">
                    <p className="text-sm leading-relaxed text-[#8888a0]">{item.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[rgba(255,255,255,0.06)] px-6 py-12">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 md:flex-row">
          <span className="text-lg font-bold glow-text">OKAMOEY</span>
          <div className="flex gap-6">
            <a href="#" className="text-xs text-[#55556a] hover:text-[#8888a0]">Terms</a>
            <a href="#" className="text-xs text-[#55556a] hover:text-[#8888a0]">Privacy</a>
            <a href="#" className="text-xs text-[#55556a] hover:text-[#8888a0]">Contact</a>
          </div>
          <p className="text-xs text-[#3a3a4a]">&copy; 2026 Okamoey. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
