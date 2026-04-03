"use client";

import { usePathname } from "next/navigation";
import { ChatPanel } from "./chat-panel";

const ROUTE_TO_AGENT: Record<string, { type: string; name: string }> = {
  "/": { type: "dashboard", name: "Dashboard Assistant" },
  "/portfolio": { type: "portfolio", name: "Portfolio Analyst" },
  "/trading": { type: "trading", name: "Trade Executor" },
  "/strategies": { type: "strategy", name: "Strategy Architect" },
  "/alerts": { type: "risk", name: "Risk Manager" },
  "/analytics": { type: "analytics", name: "Analytics Interpreter" },
};

export function ChatWrapper() {
  const pathname = usePathname();
  const agent = ROUTE_TO_AGENT[pathname] ?? ROUTE_TO_AGENT["/"];

  return <ChatPanel agentType={agent.type} agentName={agent.name} />;
}
