"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/providers/theme-provider";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  Brain,
  Bell,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Sun,
  Moon,
  Bot,
  Hand,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Crypto", href: "/crypto", icon: CircleDollarSign },
  { label: "Portfolio", href: "/portfolio", icon: Wallet },
  { label: "Trading", href: "/trading", icon: ArrowLeftRight },
  { label: "Strategies", href: "/strategies", icon: Brain },
  { label: "Alerts", href: "/alerts", icon: Bell },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const { theme, toggleTheme, tradingMode, setTradingMode } = useTheme();

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 h-full z-40 liquid-glass transition-all duration-300",
          "rounded-none rounded-r-[24px]",
          collapsed ? "w-[72px]" : "w-[280px]",
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between px-5 border-b border-[var(--glass-border)]">
          {!collapsed && (
            <span className="glow-text text-xl font-bold tracking-wider">OKAMOEY</span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex h-8 w-8 items-center justify-center rounded-xl text-[var(--text-muted)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all"
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col gap-1.5 p-3 mt-2">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "accent-bg accent-text accent-glow"
                    : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
                )}
              >
                {isActive && (
                  <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full"
                    style={{ background: "var(--page-accent)" }}
                  />
                )}
                <item.icon className={cn("h-5 w-5 shrink-0 transition-colors", isActive ? "accent-text" : "text-[var(--text-muted)] group-hover:text-[var(--foreground)]")} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Bottom controls */}
        <div className="p-3 space-y-2 border-t border-[var(--glass-border)]">
          {/* Manual/Auto toggle */}
          <button
            onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-all",
              tradingMode === "auto"
                ? "bg-[#22c55e]/15 text-[#22c55e]"
                : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]",
            )}
          >
            {tradingMode === "auto" ? <Bot className="h-5 w-5 shrink-0" /> : <Hand className="h-5 w-5 shrink-0" />}
            {!collapsed && (
              <div className="flex flex-1 items-center justify-between">
                <span>{tradingMode === "auto" ? "Auto" : "Manual"}</span>
                <div className={cn(
                  "w-9 h-5 rounded-full relative transition-colors",
                  tradingMode === "auto" ? "bg-[#22c55e]" : "bg-[var(--text-muted)]/30",
                )}>
                  <div className={cn(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform",
                    tradingMode === "auto" ? "translate-x-4" : "translate-x-0.5",
                  )} />
                </div>
              </div>
            )}
          </button>

          {/* Light/Dark toggle */}
          <button
            onClick={toggleTheme}
            className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all"
          >
            {theme === "dark" ? <Sun className="h-5 w-5 shrink-0" /> : <Moon className="h-5 w-5 shrink-0" />}
            {!collapsed && <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>}
          </button>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 liquid-glass-strong rounded-t-[20px] px-2 pb-[env(safe-area-inset-bottom)]">
        <div className="flex items-center justify-around">
          {navItems.slice(0, 5).map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2 px-3 min-w-0 transition-colors",
                  isActive ? "accent-text" : "text-[var(--text-muted)]",
                )}
              >
                <item.icon className="h-5 w-5" />
                <span className="text-[10px] font-medium truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
