"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

const PLANS = [
  { id: "starter", label: "Starter", desc: "Desk guidance and assisted execution." },
  { id: "pro", label: "Pro", desc: "Full copilot workflow for active traders." },
  { id: "elite", label: "Elite", desc: "Advanced workflow for higher-frequency operators." },
] as const;

export default function RegisterPage() {
  const router = useRouter();
  const { loginWithTokens } = useAuth();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [plan, setPlan] = useState<(typeof PLANS)[number]["id"]>("starter");
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptData, setAcceptData] = useState(false);
  const [acceptMarketing, setAcceptMarketing] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          username,
          password,
          subscription_plan: plan,
          billing_cycle: billingCycle,
          accept_terms: acceptTerms,
          terms_version: "2026-04",
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Echec de l'inscription" }));
        throw new Error(data.detail || "Echec de l'inscription");
      }
      const data = await res.json();
      // Store tokens and fetch profile via AuthProvider
      await loginWithTokens(data.access_token, data.refresh_token);
      router.push("/crypto");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Echec de l'inscription");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0d0d12] px-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(6,214,160,0.06)_0%,transparent_50%)]" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="flex items-center justify-center gap-2">
            <img src="/logo-compact.svg" alt="GlueTrade" className="h-10 w-10" /><span className="text-2xl font-bold glow-text">GlueTrade</span>
          </Link>
          <p className="mt-2 text-sm text-[#8888a0]">Create your trading account</p>
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
              placeholder="votre@email.com"
            />
          </div>

          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Nom d'utilisateur</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              autoComplete="off"
              className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
              placeholder="Nom d'utilisateur"
            />
          </div>

          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Plan</label>
            <div className="space-y-2">
              {PLANS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setPlan(item.id)}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition-all ${
                    plan === item.id
                      ? "border-[#06d6a0]/50 bg-[#06d6a0]/10"
                      : "border-[rgba(255,255,255,0.06)] bg-[#0d0d12]"
                  }`}
                >
                  <p className="text-sm font-semibold text-white">{item.label}</p>
                  <p className="mt-1 text-xs text-[#8888a0]">{item.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Billing Cycle</label>
            <div className="grid grid-cols-2 gap-2">
              {(["monthly", "yearly"] as const).map((cycle) => (
                <button
                  key={cycle}
                  type="button"
                  onClick={() => setBillingCycle(cycle)}
                  className={`rounded-xl border px-4 py-3 text-sm font-medium transition-all ${
                    billingCycle === cycle
                      ? "border-[#06d6a0]/50 bg-[#06d6a0]/10 text-white"
                      : "border-[rgba(255,255,255,0.06)] bg-[#0d0d12] text-[#8888a0]"
                  }`}
                >
                  {cycle === "monthly" ? "Monthly" : "Yearly"}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <label className="mb-1.5 block text-xs font-medium text-[#8888a0]">Mot de passe</label>
            <div className="relative">
              <input
                type={showPass ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className="w-full rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3 pr-10 text-sm text-white placeholder-[#55556a] outline-none focus:border-[#06d6a0]/40"
                placeholder="Min. 8 caracteres, 1 chiffre, 1 majuscule"
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

          {/* RGPD — Consentements obligatoires */}
          <div className="mb-4 space-y-2.5">
            <label className="flex items-start gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3">
              <input
                type="checkbox"
                checked={acceptTerms}
                onChange={(e) => setAcceptTerms(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#06d6a0]/40 bg-transparent text-[#06d6a0]"
              />
              <span className="text-xs leading-5 text-[#8888a0]">
                J&apos;accepte les{" "}
                <Link href="/terms" className="text-[#06d6a0] hover:underline">Conditions d&apos;utilisation</Link>{" "}
                et la{" "}
                <Link href="/privacy" className="text-[#06d6a0] hover:underline">Politique de confidentialite</Link>.
                <span className="text-[#ef4444]"> *</span>
              </span>
            </label>

            <label className="flex items-start gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3">
              <input
                type="checkbox"
                checked={acceptData}
                onChange={(e) => setAcceptData(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#06d6a0]/40 bg-transparent text-[#06d6a0]"
              />
              <span className="text-xs leading-5 text-[#8888a0]">
                J&apos;accepte le traitement de mes donnees personnelles (email, preferences de trading) pour le fonctionnement du service, conformement au RGPD.
                <span className="text-[#ef4444]"> *</span>
              </span>
            </label>

            <label className="flex items-start gap-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d0d12] px-4 py-3">
              <input
                type="checkbox"
                checked={acceptMarketing}
                onChange={(e) => setAcceptMarketing(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#06d6a0]/40 bg-transparent text-[#06d6a0]"
              />
              <span className="text-xs leading-5 text-[#8888a0]">
                J&apos;accepte de recevoir des communications marketing et des alertes trading par email (facultatif, desactivable a tout moment dans les reglages).
              </span>
            </label>
          </div>

          <p className="mb-4 text-[10px] text-[#55556a] leading-4">
            Vos donnees sont stockees de maniere securisee en Europe. Vous pouvez exercer vos droits (acces, rectification, suppression, portabilite) a tout moment depuis les Reglages ou en contactant support@gluetrade.com.
          </p>

          <button
            type="submit"
            disabled={loading || !acceptTerms || !acceptData}
            className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] transition-transform hover:scale-[1.01] disabled:opacity-50"
          >
            {loading ? <Loader2 className="mx-auto h-4 w-4 animate-spin" /> : "Creer mon compte"}
          </button>

          <p className="mt-4 text-center text-xs text-[#8888a0]">
            Already have an account?{" "}
            <Link href="/login" className="text-[#06d6a0] hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
