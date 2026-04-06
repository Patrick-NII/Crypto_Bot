"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ChatPanel } from "./chat-panel";

const ROUTE_TO_AGENT: Record<string, { type: string; name: string }> = {
  "/crypto": { type: "trading", name: "Trade Executor" },
  "/settings": { type: "trading", name: "Desk Assistant" },
};

export function ChatWrapper() {
  const pathname = usePathname();
  const agent = ROUTE_TO_AGENT[pathname] ?? { type: "trading", name: "Trade Executor" };
  const [externalOpen, setExternalOpen] = useState(false);

  // Listen for custom event from hamburger menu
  useEffect(() => {
    const handler = () => setExternalOpen(true);
    window.addEventListener("gluetrade-open-chat", handler);
    return () => window.removeEventListener("gluetrade-open-chat", handler);
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
    window.dispatchEvent(new Event("gluetrade-open-chat"));
  }
}
