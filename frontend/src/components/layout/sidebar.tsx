"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Portfolio", href: "/portfolio", icon: Wallet },
  { label: "Trading", href: "/trading", icon: ArrowLeftRight },
  { label: "Strategies", href: "/strategies", icon: Brain },
  { label: "Alerts", href: "/alerts", icon: Bell },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col fixed left-0 top-0 h-full z-40 glass-strong transition-all duration-300 border-r border-white/[0.06]",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {/* Logo area */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-white/[0.06]">
          {!collapsed && (
            <span className="glow-text text-lg font-bold tracking-wider">
              OKAMOEY
            </span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-white/40 hover:text-white hover:bg-white/[0.06] transition-colors"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 flex flex-col gap-1 p-3 mt-2">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-white/[0.08] text-white"
                    : "text-white/50 hover:text-white hover:bg-white/[0.04]"
                )}
              >
                {/* Active indicator */}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full bg-gradient-to-b from-accent-purple to-accent-blue shadow-[0_0_8px_rgba(168,85,247,0.5)]" />
                )}

                <item.icon
                  className={cn(
                    "h-5 w-5 shrink-0 transition-colors",
                    isActive ? "text-accent-purple" : "text-white/40 group-hover:text-white/70"
                  )}
                />
                {!collapsed && (
                  <span className="truncate">{item.label}</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="p-3 border-t border-white/[0.06]">
          <div
            className={cn(
              "flex items-center gap-3 rounded-xl px-3 py-2",
              collapsed && "justify-center"
            )}
          >
            <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-accent-purple to-accent-blue flex items-center justify-center text-xs font-bold text-white">
              OK
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-xs font-medium text-white/80 truncate">
                  Okamoey Bot
                </p>
                <p className="text-[10px] text-white/40 truncate">Active</p>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 glass-strong border-t border-white/[0.06] px-2 pb-[env(safe-area-inset-bottom)]">
        <div className="flex items-center justify-around">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex flex-col items-center gap-0.5 py-2 px-3 min-w-0 transition-colors",
                  isActive ? "text-accent-purple" : "text-white/40"
                )}
              >
                <item.icon className="h-5 w-5" />
                <span className="text-[10px] font-medium truncate">
                  {item.label}
                </span>
                {isActive && (
                  <div className="absolute top-0 h-[2px] w-8 rounded-b-full bg-gradient-to-r from-accent-purple to-accent-blue" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
