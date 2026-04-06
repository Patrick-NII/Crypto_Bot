"use client";

import Link from "next/link";
import { useState } from "react";
import { Loader2, ArrowLeft, Mail } from "lucide-react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/auth/password-reset-request`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        },
      );
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="flex items-center justify-center gap-2">GLUETRADE</Link>
          <p className="mt-2 text-sm text-[#8888a0]">Reset your password</p>
        </div>

        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8">
          {sent ? (
            <div className="text-center">
              <Mail className="mx-auto mb-4 h-12 w-12 text-[#06d6a0]" />
              <h2 className="mb-2 text-lg font-semibold text-white">Check your email</h2>
              <p className="mb-6 text-sm text-[#8888a0]">
                If an account exists for {email}, we&apos;ve sent a password reset link.
              </p>
              <Link href="/login" className="text-sm text-[#06d6a0] hover:underline">Back to login</Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <p className="mb-6 text-sm text-[#8888a0]">
                Enter your email address and we&apos;ll send you a link to reset your password.
              </p>
              <div className="mb-6">
                <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
                  placeholder="you@example.com"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] disabled:opacity-50"
              >
                {loading ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Send Reset Link"}
              </button>
              <div className="mt-4 text-center">
                <Link href="/login" className="inline-flex items-center gap-1 text-xs text-[#8888a0] hover:text-white">
                  <ArrowLeft className="h-3 w-3" /> Back to login
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
