"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "@/components/providers/theme-provider";
import { useAuth } from "@/components/providers/auth-provider";
import { openChatGlobal } from "@/components/ai/chat-wrapper";
import { cn } from "@/lib/utils";
import { VERSION_DISPLAY, APP_ENV, ENV_COLOR } from "@/lib/version";
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  Brain,
  Bell,
  BarChart3,
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
  Newspaper,
  Menu,
  X,
  Sparkles,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Trading", href: "/crypto", icon: CircleDollarSign },
  { label: "Portfolio", href: "/portfolio", icon: Wallet },
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
  const { user, clearAuth } = useAuth();

  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved === "true") setCollapsed(true);
    setMounted(true);
  }, []);

  // Close mobile menu on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem(SIDEBAR_KEY, String(next));
  };

  const handleLogout = () => {
    clearAuth();
    router.push("/login");
  };

  const sidebarW = !mounted ? "w-[240px]" : collapsed ? "w-[68px]" : "w-[240px]";

  const glassStyle = {
    background: "var(--glass-bg-strong)",
    backdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
    WebkitBackdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
    borderRight: "1px solid var(--glass-border)",
    boxShadow: "4px 0 24px var(--glass-shadow), inset -1px 0 0 var(--glass-highlight)",
  } as const;

  // Shared nav content
  function NavContent({ isMobile = false }: { isMobile?: boolean }) {
    return (
      <>
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={!isMobile && collapsed ? item.label : undefined}
              className={cn(
                "group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[15px] font-medium transition-all duration-150",
                !isMobile && collapsed && "justify-center px-0",
                isActive
                  ? "accent-bg accent-text"
                  : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
              )}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2.5px] h-5 rounded-r-full" style={{ background: "var(--page-accent)" }} />
              )}
              <item.icon className={cn("h-[18px] w-[18px] shrink-0", isActive ? "accent-text" : "text-[var(--text-muted)] group-hover:text-[var(--foreground)]")} />
              {(isMobile || !collapsed) && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </>
    );
  }

  function BottomControls({ isMobile = false }: { isMobile?: boolean }) {
    const showLabel = isMobile || !collapsed;
    const centerClass = !isMobile && collapsed ? "justify-center px-0" : "";

    return (
      <div className="px-2 pb-2 pt-1.5 space-y-0.5 border-t border-[var(--glass-border)]">
        <button
          onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
          className={cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium transition-all", centerClass, tradingMode === "auto" ? "bg-[#22c55e]/12 text-[#22c55e]" : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]")}
        >
          {tradingMode === "auto" ? <Bot className="h-4 w-4 shrink-0" /> : <Hand className="h-4 w-4 shrink-0" />}
          {showLabel && (
            <div className="flex flex-1 items-center justify-between">
              <span>{tradingMode === "auto" ? "Auto" : "Manual"}</span>
              <div className={cn("w-7 h-4 rounded-full relative transition-colors", tradingMode === "auto" ? "bg-[#22c55e]" : "bg-[var(--glass-border)]")}>
                <div className={cn("absolute top-[2px] h-3 w-3 rounded-full bg-white shadow-sm transition-transform", tradingMode === "auto" ? "translate-x-[12px]" : "translate-x-[2px]")} />
              </div>
            </div>
          )}
        </button>

        {/* AI Chat — visible in mobile drawer, hidden on desktop sidebar */}
        {isMobile && (
          <button onClick={() => { openChatGlobal(); }} className="flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium text-[#06d6a0] hover:bg-[#06d6a0]/8 transition-all">
            <Sparkles className="h-4 w-4 shrink-0" />
            <span>AI Assistant</span>
          </button>
        )}

        <Link href="/settings" className={cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all", centerClass)}>
          <Settings className="h-4 w-4 shrink-0" />
          {showLabel && <span>Settings</span>}
        </Link>

        <button onClick={toggleTheme} className={cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all", centerClass)}>
          {theme === "dark" ? <Sun className="h-4 w-4 shrink-0" /> : <Moon className="h-4 w-4 shrink-0" />}
          {showLabel && <span>{theme === "dark" ? "Light" : "Dark"}</span>}
        </button>

        <button onClick={handleLogout} className={cn("flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium text-[#ef4444]/70 hover:text-[#ef4444] hover:bg-[#ef4444]/8 transition-all", centerClass)}>
          <LogOut className="h-4 w-4 shrink-0" />
          {showLabel && <span>Log out</span>}
        </button>

        {/* Version badge */}
        <div className={cn("flex items-center gap-1.5 px-3 pt-2", centerClass)}>
          {showLabel ? (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono text-[var(--text-muted)]">{VERSION_DISPLAY}</span>
              <span
                className="rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase"
                style={{ backgroundColor: `${ENV_COLOR[APP_ENV] ?? "#888"}20`, color: ENV_COLOR[APP_ENV] ?? "#888" }}
              >
                {APP_ENV === "production" ? "prod" : APP_ENV === "staging" ? "preprod" : "dev"}
              </span>
            </div>
          ) : (
            <span className="text-[9px] font-mono text-[var(--text-muted)] truncate">{VERSION_DISPLAY}</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ─── Desktop Sidebar ─── */}
      <aside
        className={cn("hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 transition-all duration-300 ease-out", sidebarW)}
        style={glassStyle}
      >
        <div className="flex h-12 items-center justify-between px-3 border-b border-[var(--glass-border)]">
          {!collapsed ? (
            <div className="min-w-0">
              <span className="glow-text text-base font-bold tracking-wide">OKAMOEY</span>
              {user && (
                <p className="text-[10px] text-[var(--text-muted)] truncate">{user.username}</p>
              )}
            </div>
          ) : null}
          <button onClick={toggleCollapsed} className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all">
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>
        <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
          <NavContent />
        </nav>
        <BottomControls />
      </aside>

      {/* ─── Mobile Hamburger Button ─── */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between h-12 px-3"
        style={{ background: "var(--glass-bg-strong)", backdropFilter: "blur(20px) saturate(180%)", WebkitBackdropFilter: "blur(20px) saturate(180%)", borderBottom: "1px solid var(--glass-border)" }}
      >
        <button
          onClick={() => setMobileOpen(true)}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)] transition-all"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="glow-text text-sm font-bold">OKAMOEY</span>
        <div className="w-8" />
      </div>

      {/* ─── Mobile Drawer ─── */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-[70]">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />

          {/* Drawer */}
          <aside
            className="absolute left-0 top-0 bottom-0 w-[280px] flex flex-col animate-slide-in"
            style={{
              background: "var(--surface)",
              borderRight: "1px solid var(--glass-border)",
              boxShadow: "8px 0 32px var(--glass-shadow)",
            }}
          >
            {/* Header */}
            <div className="flex h-12 items-center justify-between px-4 border-b border-[var(--glass-border)]">
              <span className="glow-text text-base font-bold">OKAMOEY</span>
              <button onClick={() => setMobileOpen(false)} className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Nav */}
            <nav className="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
              <NavContent isMobile />
            </nav>

            {/* Bottom */}
            <BottomControls isMobile />
          </aside>
        </div>
      )}
    </>
  );
}
