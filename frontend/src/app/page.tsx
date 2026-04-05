"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function LandingPage() {
  return (
    <TradingOnlyRedirect
      title="Trading Workspace"
      description="This branch is dedicated to the trading desk. Redirecting to /crypto."
    />
  );
}
