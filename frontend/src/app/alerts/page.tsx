"use client";

import { TradingOnlyRedirect } from "@/components/navigation/trading-only-redirect";

export default function AlertsPage() {
  return (
    <TradingOnlyRedirect
      title="Alerts Removed"
      description="Alerting is not exposed in this trading-only workspace. Redirecting to /crypto."
    />
  );
}
