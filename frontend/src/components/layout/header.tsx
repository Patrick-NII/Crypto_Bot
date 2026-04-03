"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Search, Wifi, WifiOff, X } from "lucide-react";

interface HeaderProps {
  sidebarCollapsed?: boolean;
}

export function Header({ sidebarCollapsed = false }: HeaderProps) {
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [connected] = useState(true);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex h-16 items-center gap-4 px-4 md:px-6 bg-[rgba(13,13,18,0.8)] backdrop-blur-[12px] border-b border-[rgba(255,255,255,0.06)]"
      )}
    >
      {/* Logo - mobile only */}
      <div className="md:hidden flex items-center">
        <span className="glow-text text-lg font-bold tracking-wider">
          OKAMOEY
        </span>
      </div>

      {/* Spacer pushes search to center on desktop */}
      <div className="hidden md:block flex-1" />

      {/* Search bar */}
      <div
        className={cn(
          "relative flex-1 md:flex-none md:w-80 transition-all duration-300",
          searchFocused && "md:w-96"
        )}
      >
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#55556a]" />
        <input
          type="text"
          placeholder="Search assets..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
          className={cn(
            "w-full h-9 rounded-xl bg-[#14141b] border border-[rgba(255,255,255,0.06)] pl-9 pr-3 text-sm text-[#e8e8ed] placeholder:text-[#55556a] outline-none transition-all duration-200 ease-out",
            "focus:border-[#06d6a0]/40 focus:shadow-[0_0_0_3px_rgba(6,214,160,0.1)]"
          )}
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#55556a] hover:text-[#8888a0]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3">
        {/* Connection status */}
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium",
            connected
              ? "text-[#06d6a0] bg-[#06d6a0]/10"
              : "text-red-400 bg-red-500/10"
          )}
        >
          {connected ? (
            <Wifi className="h-3.5 w-3.5" />
          ) : (
            <WifiOff className="h-3.5 w-3.5" />
          )}
          <span className="hidden sm:inline">
            {connected ? "Connected" : "Disconnected"}
          </span>
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              connected
                ? "bg-[#06d6a0] shadow-[0_0_6px_rgba(6,214,160,0.6)]"
                : "bg-red-400 shadow-[0_0_6px_rgba(239,68,68,0.6)]"
            )}
          />
        </div>
      </div>
    </header>
  );
}
