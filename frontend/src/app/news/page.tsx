"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function NewsPage() {
  return (
    <TradingOnlyRedirect
      title="News Removed"
      description="This Trading branch keeps only the execution desk. Redirecting to /crypto."
    />
  );
}
