"use client";

import { Search, Wifi } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function Header() {
  const [focused, setFocused] = useState(false);

  return (
    <header
      className="sticky top-0 z-30 border-b border-[var(--glass-border)]"
      style={{
        background: "var(--glass-bg)",
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
      }}
    >
      <div className="flex h-14 items-center justify-between gap-3 px-3 md:px-5">
        {/* Mobile logo */}
        <span className="md:hidden glow-text text-base font-bold">OKAMOEY</span>

        <div className="hidden md:block flex-1" />

        {/* Search */}
        <div
          className={cn(
            "relative flex items-center rounded-full px-3 py-1.5 transition-all duration-300",
            focused ? "flex-1 md:flex-none md:w-80 ring-1 ring-[var(--page-accent)]/30" : "flex-1 md:flex-none md:w-56",
          )}
          style={{
            background: "var(--glass-bg)",
            border: "1px solid var(--glass-border)",
          }}
        >
          <Search className="mr-2 h-3.5 w-3.5 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search assets..."
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            className="w-full bg-transparent text-xs text-[var(--foreground)] placeholder-[var(--text-muted)] outline-none"
          />
        </div>

        {/* Status */}
        <div className="flex items-center gap-1.5 rounded-full px-2.5 py-1" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
          <Wifi className="h-3 w-3 accent-text" />
          <span className="hidden sm:inline text-[11px] font-medium accent-text">Live</span>
          <div className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: "var(--page-accent)" }} />
        </div>
      </div>
    </header>
  );
}
