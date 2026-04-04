"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "@/components/providers/theme-provider";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  Brain,
  Bell,
  BarChart3,
  Newspaper,
  PanelLeftClose,
  PanelLeftOpen,
  CircleDollarSign,
  Sun,
  Moon,
  Bot,
  Hand,
  User,
  Settings,
  LogOut,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Crypto", href: "/crypto", icon: CircleDollarSign },
  { label: "Portfolio", href: "/portfolio", icon: Wallet },
  { label: "Trading", href: "/trading", icon: ArrowLeftRight },
  { label: "Strategies", href: "/strategies", icon: Brain },
  { label: "News", href: "/news", icon: Newspaper },
  { label: "Alerts", href: "/alerts", icon: Bell },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
] as const;

const SIDEBAR_KEY = "okamoey-sidebar-collapsed";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme, tradingMode, setTradingMode } = useTheme();

  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved === "true") setCollapsed(true);
    setMounted(true);
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(SIDEBAR_KEY, String(next));
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("demo_user");
    router.push("/login");
  };

  const sidebarW = !mounted ? "w-[240px]" : collapsed ? "w-[68px]" : "w-[240px]";

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 transition-all duration-300 ease-out",
          sidebarW,
        )}
        style={{
          background: "var(--glass-bg-strong)",
          backdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
          WebkitBackdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
          borderRight: "1px solid var(--glass-border)",
          boxShadow: "4px 0 24px var(--glass-shadow), inset -1px 0 0 var(--glass-highlight)",
        }}
      >
        {/* Logo */}
        <div className="flex h-12 items-center justify-between px-3 border-b border-[var(--glass-border)]">
          {!collapsed && (
            <span className="glow-text text-base font-bold tracking-wide">OKAMOEY</span>
          )}
          <button
            onClick={toggleCollapsed}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition-all duration-150",
                  collapsed && "justify-center px-0",
                  isActive
                    ? "accent-bg accent-text"
                    : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
                )}
              >
                {isActive && (
                  <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-[2.5px] h-5 rounded-r-full"
                    style={{ background: "var(--page-accent)" }}
                  />
                )}
                <item.icon className={cn("h-[18px] w-[18px] shrink-0", isActive ? "accent-text" : "text-[var(--text-muted)] group-hover:text-[var(--foreground)]")} />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Bottom controls */}
        <div className="px-2 pb-2 pt-1.5 space-y-0.5 border-t border-[var(--glass-border)]">
          {/* Manual/Auto toggle */}
          <button
            onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium transition-all",
              collapsed && "justify-center px-0",
              tradingMode === "auto"
                ? "bg-[#22c55e]/12 text-[#22c55e]"
                : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]",
            )}
          >
            {tradingMode === "auto" ? <Bot className="h-4 w-4 shrink-0" /> : <Hand className="h-4 w-4 shrink-0" />}
            {!collapsed && (
              <div className="flex flex-1 items-center justify-between">
                <span>{tradingMode === "auto" ? "Auto" : "Manual"}</span>
                <div className={cn(
                  "w-7 h-4 rounded-full relative transition-colors",
                  tradingMode === "auto" ? "bg-[#22c55e]" : "bg-[var(--glass-border)]",
                )}>
                  <div className={cn(
                    "absolute top-[2px] h-3 w-3 rounded-full bg-white shadow-sm transition-transform",
                    tradingMode === "auto" ? "translate-x-[12px]" : "translate-x-[2px]",
                  )} />
                </div>
              </div>
            )}
          </button>

          {/* Account */}
          <Link
            href="/dashboard"
            title={collapsed ? "Account" : undefined}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all",
              collapsed && "justify-center px-0",
            )}
          >
            <User className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Account</span>}
          </Link>

          {/* Settings */}
          <Link
            href="/settings"
            title={collapsed ? "Settings" : undefined}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all",
              collapsed && "justify-center px-0",
            )}
          >
            <Settings className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Settings</span>}
          </Link>

          {/* Light/Dark */}
          <button
            onClick={toggleTheme}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all",
              collapsed && "justify-center px-0",
            )}
          >
            {theme === "dark" ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
            {!collapsed && <span>{theme === "dark" ? "Light" : "Dark"}</span>}
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium text-[#ef4444]/70 hover:text-[#ef4444] hover:bg-[#ef4444]/8 transition-all",
              collapsed && "justify-center px-0",
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Log out</span>}
          </button>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 pb-[env(safe-area-inset-bottom)]"
        style={{
          background: "var(--glass-bg-strong)",
          backdropFilter: "blur(24px) saturate(180%)",
          WebkitBackdropFilter: "blur(24px) saturate(180%)",
          borderTop: "1px solid var(--glass-border)",
          boxShadow: "0 -4px 20px var(--glass-shadow)",
        }}
      >
        <div className="flex items-center justify-around px-1">
          {navItems.slice(0, 5).map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2.5 px-2 min-w-0 transition-colors",
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
