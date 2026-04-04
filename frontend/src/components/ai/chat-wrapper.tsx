"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ChatPanel } from "./chat-panel";

const ROUTE_TO_AGENT: Record<string, { type: string; name: string }> = {
  "/dashboard": { type: "dashboard", name: "Dashboard Assistant" },
  "/crypto": { type: "trading", name: "Trade Executor" },
  "/portfolio": { type: "portfolio", name: "Portfolio Analyst" },
  "/strategies": { type: "strategy", name: "Strategy Architect" },
  "/alerts": { type: "risk", name: "Risk Manager" },
  "/analytics": { type: "analytics", name: "Analytics Interpreter" },
  "/news": { type: "dashboard", name: "Market Analyst" },
  "/settings": { type: "dashboard", name: "AI Assistant" },
};

export function ChatWrapper() {
  const pathname = usePathname();
  const agent = ROUTE_TO_AGENT[pathname] ?? { type: "dashboard", name: "AI Assistant" };
  const [externalOpen, setExternalOpen] = useState(false);

  // Listen for custom event from hamburger menu
  useEffect(() => {
    const handler = () => setExternalOpen(true);
    window.addEventListener("okamoey-open-chat", handler);
    return () => window.removeEventListener("okamoey-open-chat", handler);
  }, []);

  return (
    <ChatPanel
      agentType={agent.type}
      agentName={agent.name}
      externalOpen={externalOpen}
      onExternalClose={() => setExternalOpen(false)}
    />
  );
}

/** Call this to open chat from anywhere (e.g., hamburger menu) */
export function openChatGlobal() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("okamoey-open-chat"));
  }
}
