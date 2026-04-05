"use client";

import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8">
        <Link href="/" className="text-sm text-[var(--page-accent)] hover:underline">
          Back to home
        </Link>
        <h1 className="mt-3 text-3xl font-bold text-[var(--foreground)]">Terms & Conditions</h1>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          Version 2026-04. This page summarises the operational rules of the platform.
        </p>
      </div>

      <div className="space-y-6 text-sm leading-7 text-[var(--text-secondary)]">
        <section>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Access</h2>
          <p>
            Opening an account requires acceptance of these terms. Market information can be explored without a connected
            wallet, but all wallet-related features remain locked until the user configures their own exchange connection.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">User Credentials</h2>
          <p>
            Each user is responsible for their own exchange API keys and wallet connectivity. Keys should be created with
            the minimum permissions required, starting with read-only access whenever possible.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Risk Disclosure</h2>
          <p>
            The platform provides analytics, execution tooling and AI-assisted guidance. It does not guarantee profits.
            Trading digital assets involves material risk, including partial or total loss of capital.
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Subscription</h2>
          <p>
            Product access may depend on the selected plan, billing cycle and subscription status. Premium execution and
            wallet features can be restricted when the subscription is inactive, expired or past due.
          </p>
        </section>
      </div>
    </div>
  );
}
