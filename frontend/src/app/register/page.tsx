"use client";

import Link from "next/link";
import { useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/auth/register`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, username, password }),
        },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Registration failed" }));
        throw new Error(data.detail || "Registration failed");
      }
      const data = await res.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="text-2xl font-bold glow-text">OKAMOEY</Link>
          <p className="mt-2 text-sm text-[#8888a0]">Create your trading account</p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#14141b] p-8">
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
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
              placeholder="you@example.com"
            />
          </div>

          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
              placeholder="Choose a username"
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
                minLength={8}
                className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 pr-10 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
                placeholder="Min. 8 characters"
              />
              <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#55556a]">
                {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] transition-transform hover:scale-[1.01] disabled:opacity-50"
          >
            {loading ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Create Account"}
          </button>

          <p className="mt-4 text-center text-xs text-[#8888a0]">
            Already have an account?{" "}
            <Link href="/login" className="text-[#06d6a0] hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
