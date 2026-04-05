"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function DashboardPage() {
  return (
    <TradingOnlyRedirect
      title="Dashboard Removed"
      description="This Trading branch only keeps the trading desk. Redirecting to /crypto."
    />
  );
}
