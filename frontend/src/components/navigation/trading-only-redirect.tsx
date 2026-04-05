"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { CircleDollarSign, Loader2 } from "lucide-react";

export function TradingOnlyRedirect({
  title = "Trading Desk",
  description = "This workspace is focused on the trading desk. Redirecting to /crypto.",
}: {
  title?: string;
  description?: string;
}) {
  const router = useRouter();

  useEffect(() => {
    router.replace("/crypto");
  }, [router]);

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <div className="relative">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)]">
            <CircleDollarSign className="h-6 w-6 accent-text" />
          </div>
          <Loader2 className="absolute -bottom-1 -right-1 h-5 w-5 animate-spin text-[var(--text-muted)]" />
        </div>
        <div>
          <p className="text-sm font-semibold text-[var(--foreground)]">{title}</p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        </div>
      </div>
    </div>
  );
}
