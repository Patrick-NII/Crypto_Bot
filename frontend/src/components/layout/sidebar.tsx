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
  PanelLeftClose,
  PanelLeftOpen,
  CircleDollarSign,
  Sun,
  Moon,
  Bot,
  Hand,
  Settings,
  LogOut,
  Menu,
  X,
  Sparkles,
} from "lucide-react";

const SIDEBAR_KEY = "gluetrade-sidebar-collapsed";

function readCollapsedPreference() {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(SIDEBAR_KEY) === "true";
}

function TradingNavLink({
  collapsed,
  href,
  label,
  isActive,
  onClick,
}: {
  collapsed: boolean;
  href: string;
  label: string;
  isActive: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      title={collapsed ? label : undefined}
      className={cn(
        "group relative flex items-center gap-2.5 rounded-xl px-3 py-2 text-[15px] font-medium transition-all duration-150",
        collapsed && "justify-center px-0",
        isActive
          ? "accent-bg accent-text"
          : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
      )}
    >
      {isActive ? (
        <div
          className="absolute left-0 top-1/2 h-5 w-[2.5px] -translate-y-1/2 rounded-r-full"
          style={{ background: "var(--page-accent)" }}
        />
      ) : null}
      <CircleDollarSign
        className={cn(
          "h-[18px] w-[18px] shrink-0",
          isActive ? "accent-text" : "text-[var(--text-muted)] group-hover:text-[var(--foreground)]",
        )}
      />
      {!collapsed ? <span className="truncate">{label}</span> : null}
    </Link>
  );
}

function SidebarActionButton({
  collapsed,
  isMobile,
  className,
  icon,
  label,
  rightContent,
  onClick,
}: {
  collapsed: boolean;
  isMobile?: boolean;
  className?: string;
  icon: React.ReactNode;
  label: string;
  rightContent?: React.ReactNode;
  onClick: () => void;
}) {
  const showLabel = isMobile || !collapsed;
  const centerClass = !isMobile && collapsed ? "justify-center px-0" : "";

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-xl px-3 py-1.5 text-[14px] font-medium transition-all",
        centerClass,
        className,
      )}
    >
      <span className="shrink-0">{icon}</span>
      {showLabel ? (
        <div className="flex flex-1 items-center justify-between">
          <span>{label}</span>
          {rightContent}
        </div>
      ) : null}
    </button>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme, tradingMode, setTradingMode } = useTheme();
  const { user, clearAuth } = useAuth();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Sync collapsed state from localStorage after mount (avoid hydration mismatch)
  useEffect(() => {
    const stored = localStorage.getItem(SIDEBAR_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(SIDEBAR_KEY, String(next));
    }
  };

  const handleLogout = () => {
    clearAuth();
    setMobileOpen(false);
    router.push("/login");
  };

  const closeMobile = () => setMobileOpen(false);
  const desktopSidebarWidth = collapsed ? "w-[68px]" : "w-[240px]";
  const isTradingActive = pathname.startsWith("/crypto");

  const glassStyle = {
    background: "var(--glass-bg-strong)",
    backdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
    WebkitBackdropFilter: "blur(24px) saturate(180%) brightness(1.06)",
    borderRight: "1px solid var(--glass-border)",
    boxShadow: "4px 0 24px var(--glass-shadow), inset -1px 0 0 var(--glass-highlight)",
  } as const;

  const versionBadge = (
    <div className={cn("flex items-center gap-1.5 px-3 pt-2", collapsed && "justify-center px-0")}>
      {!collapsed ? (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-[var(--text-muted)]">{VERSION_DISPLAY}</span>
          <span
            className="rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase"
            style={{
              backgroundColor: `${ENV_COLOR[APP_ENV] ?? "#888"}20`,
              color: ENV_COLOR[APP_ENV] ?? "#888",
            }}
          >
            {APP_ENV === "production" ? "prod" : APP_ENV === "staging" ? "preprod" : "dev"}
          </span>
        </div>
      ) : (
        <span className="truncate text-[9px] font-mono text-[var(--text-muted)]">{VERSION_DISPLAY}</span>
      )}
    </div>
  );

  const footer = (isMobile = false) => (
    <div className="space-y-0.5 border-t border-[var(--glass-border)] px-2 pb-2 pt-1.5">
      <SidebarActionButton
        collapsed={collapsed}
        isMobile={isMobile}
        className={
          tradingMode === "auto"
            ? "bg-[#22c55e]/12 text-[#22c55e]"
            : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
        }
        icon={
          tradingMode === "auto" ? <Bot className="h-4 w-4" /> : <Hand className="h-4 w-4" />
        }
        label={tradingMode === "auto" ? "Auto" : "Manual"}
        rightContent={
          <div
            className={cn(
              "relative h-4 w-7 rounded-full transition-colors",
              tradingMode === "auto" ? "bg-[#22c55e]" : "bg-[var(--glass-border)]",
            )}
          >
            <div
              className={cn(
                "absolute top-[2px] h-3 w-3 rounded-full bg-white shadow-sm transition-transform",
                tradingMode === "auto" ? "translate-x-[12px]" : "translate-x-[2px]",
              )}
            />
          </div>
        }
        onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
      />

      {isMobile ? (
        <SidebarActionButton
          collapsed={collapsed}
          isMobile
          className="text-[#06d6a0] hover:bg-[#06d6a0]/8"
          icon={<Sparkles className="h-4 w-4" />}
          label="AI Assistant"
          onClick={() => {
            closeMobile();
            openChatGlobal();
          }}
        />
      ) : null}

      <SidebarActionButton
        collapsed={collapsed}
        isMobile={isMobile}
        className="text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
        icon={<Settings className="h-4 w-4" />}
        label="Settings"
        onClick={() => {
          closeMobile();
          router.push("/settings");
        }}
      />

      <SidebarActionButton
        collapsed={collapsed}
        isMobile={isMobile}
        className="text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
        icon={theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        label={theme === "dark" ? "Light" : "Dark"}
        onClick={toggleTheme}
      />

      <SidebarActionButton
        collapsed={collapsed}
        isMobile={isMobile}
        className="text-[#ef4444]/70 hover:bg-[#ef4444]/8 hover:text-[#ef4444]"
        icon={<LogOut className="h-4 w-4" />}
        label="Log out"
        onClick={handleLogout}
      />

      {versionBadge}
    </div>
  );

  return (
    <>
      <aside
        className={cn(
          "fixed bottom-0 left-0 top-0 z-40 hidden flex-col transition-all duration-300 ease-out md:flex",
          desktopSidebarWidth,
        )}
        style={glassStyle}
      >
        <div className="flex h-12 items-center justify-between border-b border-[var(--glass-border)] px-3">
          {!collapsed ? (
            <div className="min-w-0 flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo-compact.svg" alt="GT" className="h-7 w-7" />
              <div>
                <span className="glow-text text-base font-bold tracking-wide">GlueTrade</span>
                {user ? <p className="truncate text-[10px] text-[var(--text-muted)]">{user.username}</p> : null}
              </div>
            </div>
          ) : (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src="/logo-compact.svg" alt="GT" className="h-6 w-6" />
          )}
          <button
            onClick={toggleCollapsed}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] transition-all hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)]"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-3">
          <TradingNavLink
            collapsed={collapsed}
            href="/crypto"
            label="Trading"
            isActive={isTradingActive}
          />
        </nav>

        {footer(false)}
      </aside>

      <div
        className="fixed left-0 right-0 top-0 z-50 flex h-12 items-center justify-between px-3 md:hidden"
        style={{
          background: "var(--glass-bg-strong)",
          backdropFilter: "blur(20px) saturate(180%)",
          WebkitBackdropFilter: "blur(20px) saturate(180%)",
          borderBottom: "1px solid var(--glass-border)",
        }}
      >
        <button
          onClick={() => setMobileOpen(true)}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] transition-all hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)]"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-1.5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-compact.svg" alt="GT" className="h-5 w-5" />
          <span className="glow-text text-sm font-bold">GlueTrade</span>
        </div>
        <div className="w-8" />
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-[70] md:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeMobile} />
          <aside
            className="absolute bottom-0 left-0 top-0 flex w-[280px] flex-col animate-slide-in"
            style={{
              background: "var(--surface)",
              borderRight: "1px solid var(--glass-border)",
              boxShadow: "8px 0 32px var(--glass-shadow)",
            }}
          >
            <div className="flex h-12 items-center justify-between border-b border-[var(--glass-border)] px-4">
              <div className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-compact.svg" alt="GT" className="h-6 w-6" />
                <span className="glow-text text-base font-bold">GlueTrade</span>
              </div>
              <button
                onClick={closeMobile}
                className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-3">
              <TradingNavLink
                collapsed={false}
                href="/crypto"
                label="Trading"
                isActive={isTradingActive}
                onClick={closeMobile}
              />
            </nav>

            {footer(true)}
          </aside>
        </div>
      ) : null}
    </>
  );
}
