"use client";

import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, Eye, EyeOff, Loader2 } from "lucide-react";
import { Suspense } from "react";

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/auth/password-reset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token, new_password: password }),
        },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Reset failed" }));
        throw new Error(data.detail || "Reset failed");
      }
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8 text-center">
        <p className="text-sm text-red-400">Invalid reset link.</p>
        <Link href="/forgot-password" className="mt-4 inline-block text-sm text-[#06d6a0] hover:underline">Request a new one</Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8 text-center">
        <CheckCircle className="mx-auto mb-4 h-12 w-12 text-[#06d6a0]" />
        <h2 className="mb-2 text-lg font-semibold text-white">Password reset!</h2>
        <p className="mb-6 text-sm text-[#8888a0]">You can now sign in with your new password.</p>
        <Link href="/login" className="rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] px-6 py-2.5 text-sm font-semibold text-[#0d0d12]">Sign In</Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8">
      {error && <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}
      <h2 className="mb-2 text-lg font-semibold text-white">Set new password</h2>
      <p className="mb-6 text-sm text-[#8888a0]">Choose a strong password with at least 8 characters.</p>
      <div className="mb-6">
        <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">New Password</label>
        <div className="relative">
          <input
            type={showPass ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 pr-10 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
            placeholder="Min. 8 characters"
          />
          <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#55556a]">
            {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <button type="submit" disabled={loading} className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] disabled:opacity-50">
        {loading ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Reset Password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold glow-text">OKAMOEY</Link>
        </div>
        <Suspense fallback={<div className="text-center text-[#8888a0]">Loading...</div>}>
          <ResetPasswordContent />
        </Suspense>
      </div>
    </div>
  );
}
