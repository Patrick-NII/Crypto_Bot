"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Suspense } from "react";

function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const effectiveStatus = token ? status : "error";

  useEffect(() => {
    if (!token) return;

    fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/auth/verify-email`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      },
    )
      .then((res) => {
        setStatus(res.ok ? "success" : "error");
      })
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8 text-center">
      {effectiveStatus === "loading" && (
        <>
          <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-[#06d6a0]" />
          <p className="text-sm text-[#8888a0]">Verifying your email...</p>
        </>
      )}
      {effectiveStatus === "success" && (
        <>
          <CheckCircle className="mx-auto mb-4 h-12 w-12 text-[#06d6a0]" />
          <h2 className="mb-2 text-lg font-semibold text-white">Email verified!</h2>
          <p className="mb-6 text-sm text-[#8888a0]">Your account is now fully activated.</p>
          <Link href="/crypto" className="rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] px-6 py-2.5 text-sm font-semibold text-[#0d0d12]">
            Open Trading Desk
          </Link>
        </>
      )}
      {effectiveStatus === "error" && (
        <>
          <XCircle className="mx-auto mb-4 h-12 w-12 text-red-400" />
          <h2 className="mb-2 text-lg font-semibold text-white">Verification failed</h2>
          <p className="mb-6 text-sm text-[#8888a0]">The link may have expired or is invalid.</p>
          <Link href="/login" className="text-sm text-[#06d6a0] hover:underline">Back to login</Link>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold glow-text">OKAMOEY</Link>
        </div>
        <Suspense fallback={<div className="text-center text-[#8888a0]">Loading...</div>}>
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
