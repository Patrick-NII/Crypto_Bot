"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function PortfolioPage() {
  return (
    <TradingOnlyRedirect
      title="Portfolio Removed"
      description="This Trading branch focuses on execution and market flow. Redirecting to /crypto."
    />
  );
}
