"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function StrategiesPage() {
  return (
    <TradingOnlyRedirect
      title="Strategies Removed"
      description="Strategy management is out of scope for this Trading branch. Redirecting to /crypto."
    />
  );
}
