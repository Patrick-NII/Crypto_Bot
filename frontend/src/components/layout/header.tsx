"use client";

import { Search, Wifi } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function Header() {
  const [focused, setFocused] = useState(false);

  return (
    <header className="sticky top-0 z-30 liquid-glass rounded-none border-0 border-b border-[var(--glass-border)]">
      <div className="flex h-16 items-center justify-between gap-4 px-4 md:px-6">
        <span className="md:hidden glow-text text-lg font-bold">OKAMOEY</span>

        <div className="hidden md:block flex-1" />

        <div
          className={cn(
            "relative flex items-center liquid-glass-pill px-4 py-2 transition-all duration-300",
            focused ? "flex-1 md:flex-none md:w-96 ring-1 ring-[var(--page-accent)]/40" : "flex-1 md:flex-none md:w-64",
          )}
        >
          <Search className="mr-2 h-4 w-4 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search assets..."
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            className="w-full bg-transparent text-sm text-[var(--foreground)] placeholder-[var(--text-muted)] outline-none"
          />
        </div>

        <div className="flex items-center gap-2 liquid-glass-pill px-3 py-1.5">
          <Wifi className="h-3.5 w-3.5 accent-text" />
          <span className="hidden sm:inline text-xs font-medium accent-text">Connected</span>
          <div className="h-2 w-2 rounded-full animate-pulse" style={{ background: "var(--page-accent)" }} />
        </div>
      </div>
    </header>
  );
}
