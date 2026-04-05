"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

export default function LoginPage() {
  const router = useRouter();
  const { loginWithTokens } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const enterDemo = async () => {
    localStorage.setItem("access_token", "demo-token");
    localStorage.setItem("refresh_token", "demo-refresh");
    localStorage.setItem(
      "demo_user",
      JSON.stringify({
        id: "demo-001",
        email: "demo@okamoey.com",
        username: "DemoTrader",
        subscription_plan: "pro",
        subscription_status: "trial",
        billing_cycle: "monthly",
        terms_version: "2026-04",
        accepted_terms_at: new Date().toISOString(),
        ai_behavior_style: "balanced",
        ai_assistant_tone: "analytical",
        wallet_access_enabled: false,
        wallet_access_reason: "Demo mode does not expose private wallet data.",
        connected_exchanges_count: 0,
        live_trading_enabled: false,
      }),
    );
    // Use loginWithTokens so AuthProvider picks up the demo state
    await loginWithTokens("demo-token", "demo-refresh");
    router.push("/dashboard");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Login failed" }));
        throw new Error(data.detail || "Login failed");
      }
      const data = await res.json();
      // Store tokens and fetch profile via AuthProvider
      await loginWithTokens(data.access_token, data.refresh_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold glow-text">
            OKAMOEY
          </Link>
          <p className="mt-2 text-sm text-[#8888a0]">Sign in to your account</p>
        </div>

        <form
          onSubmit={handleSubmit}
          autoComplete="off"
          className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8"
        >
          {error && (
            <div className="mb-4 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</div>
          )}

          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="off"
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
              placeholder="you@example.com"
            />
          </div>

          <div className="mb-6">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Password</label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 pr-10 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
                placeholder="Enter password"
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#55556a]"
              >
                {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] transition-transform hover:scale-[1.01] disabled:opacity-50"
          >
            {loading ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Sign In"}
          </button>

          <div className="mt-4 flex items-center justify-between text-xs">
            <Link href="/forgot-password" className="text-[#06d6a0] hover:underline">
              Forgot password?
            </Link>
            <Link href="/register" className="text-[#8888a0] hover:text-white">
              Create account
            </Link>
          </div>

          <div className="mt-6 border-t border-[rgba(255,255,255,0.06)] pt-6">
            <button
              type="button"
              onClick={() => void enterDemo()}
              className="w-full rounded-xl border border-[#c6f135]/30 bg-[#c6f135]/10 py-3 text-sm font-semibold text-[#c6f135] transition-all hover:bg-[#c6f135]/20"
            >
              Enter Demo Mode
            </button>
            <p className="mt-2 text-center text-[12px] text-[#55556a]">
              demo@okamoey.com &middot; No backend required
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
