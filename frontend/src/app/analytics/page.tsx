"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function AnalyticsPage() {
  return (
    <TradingOnlyRedirect
      title="Analytics Removed"
      description="This Trading branch only exposes the live desk. Redirecting to /crypto."
    />
  );
}
