"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePageAccent, useTheme } from "@/components/providers/theme-provider";
import { useAuth } from "@/components/providers/auth-provider";
import {
  useCurrency,
  CURRENCIES,
  type CurrencyCode,
} from "@/components/providers/currency-provider";
import { authApi, riskApi } from "@/lib/api";
import type {
  AIBehaviorStyle,
  AIAssistantTone,
  ExchangeConnection,
  ExchangeProviderGuide,
  RiskProfileId,
  SubscriptionPlan,
  UserProfile,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Bell,
  Bot,
  Check,
  Hand,
  Key,
  Palette,
  Shield,
  Trash2,
  User,
} from "lucide-react";

const RISK_PROFILES = [
  { id: "conservative", label: "Conservative", desc: "Lower risk and tighter trade sizing." },
  { id: "moderate", label: "Moderate", desc: "Balanced risk and return profile." },
  { id: "aggressive", label: "Aggressive", desc: "Higher conviction and faster positioning." },
] as const;

const SUBSCRIPTION_PLANS: Array<{
  id: SubscriptionPlan;
  label: string;
  desc: string;
}> = [
  { id: "discover", label: "Discover", desc: "Market visibility and onboarding." },
  { id: "starter", label: "Starter", desc: "Wallet sync and assisted execution." },
  { id: "pro", label: "Pro", desc: "Full trading copilot with richer guidance." },
  { id: "elite", label: "Elite", desc: "Advanced desk workflow and higher-touch automation." },
];

const AI_BEHAVIOR_OPTIONS: Array<{
  id: AIBehaviorStyle;
  label: string;
  desc: string;
}> = [
  { id: "gentle", label: "Gentle", desc: "Low-pressure guidance, softer alerts." },
  { id: "balanced", label: "Balanced", desc: "Default operating mode for most users." },
  { id: "assertive", label: "Assertive", desc: "Direct recommendations and stronger prioritisation." },
  { id: "aggressive", label: "Aggressive", desc: "High-urgency suggestions for fast-moving desks." },
];

const AI_TONE_OPTIONS: Array<{
  id: AIAssistantTone;
  label: string;
  desc: string;
}> = [
  { id: "concise", label: "Concise", desc: "Short operational answers." },
  { id: "coach", label: "Coach", desc: "More guidance and behavioural framing." },
  { id: "analytical", label: "Analytical", desc: "Data-first reasoning and structured trade logic." },
];

function SettingSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof User;
  children: React.ReactNode;
}) {
  return (
    <div className="liquid-glass-card p-5 space-y-4">
      <div className="flex items-center gap-2.5">
        <Icon className="h-4.5 w-4.5 accent-text" />
        <h2 className="text-sm font-semibold text-[var(--foreground)]">{title}</h2>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Toggle({
  enabled,
  onChange,
  label,
}: {
  enabled: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button onClick={onChange} className="flex w-full items-center justify-between py-1.5">
      <span className="text-[15px] text-[var(--text-secondary)]">{label}</span>
      <div
        className={cn(
          "w-9 h-5 rounded-full relative transition-colors",
          enabled ? "bg-[var(--page-accent)]" : "bg-[var(--glass-border)]",
        )}
      >
        <div
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            enabled ? "translate-x-4" : "translate-x-0.5",
          )}
        />
      </div>
    </button>
  );
}

function ChoiceCard({
  active,
  title,
  description,
  onClick,
}: {
  active: boolean;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-xl border px-3 py-3 text-left transition-all",
        active ? "accent-bg ring-1 ring-[var(--page-accent)]/35" : "hover:bg-[var(--glass-bg)]",
      )}
      style={{ borderColor: "var(--glass-border)" }}
    >
      <p className={cn("text-[15px] font-medium", active ? "accent-text" : "text-[var(--foreground)]")}>
        {title}
      </p>
      <p className="mt-1 text-[13px] text-[var(--text-muted)]">{description}</p>
    </button>
  );
}

export default function SettingsPage() {
  usePageAccent("#8b5cf6", "139,92,246");

  const { theme, toggleTheme, tradingMode, setTradingMode } = useTheme();
  const { currency, setCurrency } = useCurrency();
  const { user: authUser, refreshUser: refreshAuthUser } = useAuth();

  const readBooleanPref = (key: string, fallback: boolean) => {
    if (typeof window === "undefined") return fallback;
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : raw === "true";
  };

  const [notifEmail, setNotifEmail] = useState(() => readBooleanPref("gluetrade-notif-email", true));
  const [notifPush, setNotifPush] = useState(() => readBooleanPref("gluetrade-notif-push", false));
  const [notifTelegram, setNotifTelegram] = useState(() => readBooleanPref("gluetrade-notif-telegram", false));
  const [saved, setSaved] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [riskProfile, setRiskProfile] = useState<RiskProfileId>("moderate");
  const [providers, setProviders] = useState<ExchangeProviderGuide[]>([]);
  const [connections, setConnections] = useState<ExchangeConnection[]>([]);
  const [savingConnection, setSavingConnection] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [provider, setProvider] = useState("binance");
  const [connectionLabel, setConnectionLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [sandboxMode, setSandboxMode] = useState(false);
  const [canTrade, setCanTrade] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState("");

  const flash = () => {
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1500);
  };

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    const [profileResult, meResult, providersResult, connectionsResult] = await Promise.allSettled([
      riskApi.getProfile(),
      authApi.getMe(),
      authApi.getExchangeProviders(),
      authApi.listExchangeConnections(),
    ]);

    if (profileResult.status === "fulfilled") {
      setRiskProfile(
        profileResult.value.profile_id === "custom" ? "moderate" : profileResult.value.profile_id,
      );
    }

    if (meResult.status === "fulfilled") {
      setUser(meResult.value);
      if (meResult.value.risk_profile && meResult.value.risk_profile !== "custom") {
        setRiskProfile(meResult.value.risk_profile);
      }
    }

    if (providersResult.status === "fulfilled") {
      setProviders(providersResult.value);
      setProvider((current) => current || providersResult.value[0]?.provider || "binance");
    }

    if (connectionsResult.status === "fulfilled") {
      setConnections(connectionsResult.value);
    }

    if (
      meResult.status === "rejected" &&
      providersResult.status === "rejected" &&
      connectionsResult.status === "rejected"
    ) {
      setError("Unable to load account settings.");
    }

    setLoading(false);
  };

  useEffect(() => {
    void loadSettings();
  }, []);

  const selectedProvider = useMemo(
    () => providers.find((item) => item.provider === provider) ?? null,
    [provider, providers],
  );

  const saveRiskProfile = async (id: Exclude<RiskProfileId, "custom">) => {
    setRiskProfile(id);
    try {
      await riskApi.setProfilePreset(id);
      setUser((current) => (current ? { ...current, risk_profile: id } : current));
      flash();
    } catch {
      setError("Unable to update risk profile.");
    }
  };

  const saveUserProfile = async (patch: Partial<UserProfile>) => {
    try {
      const next = await authApi.updateMe({
        username: patch.username,
        risk_profile: patch.risk_profile,
        subscription_plan: patch.subscription_plan,
        billing_cycle: patch.billing_cycle,
        ai_behavior_style: patch.ai_behavior_style,
        ai_assistant_tone: patch.ai_assistant_tone,
      });
      setUser(next);
      void refreshAuthUser(); // sync AuthProvider
      flash();
    } catch {
      setError("Unable to save account preferences.");
    }
  };

  const handleAcceptTerms = async () => {
    try {
      const next = await authApi.acceptTerms("2026-04");
      setUser(next);
      void refreshAuthUser(); // sync AuthProvider
      flash();
    } catch {
      setError("Unable to record terms acceptance.");
    }
  };

  const handleCreateConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingConnection(true);
    setError(null);
    try {
      await authApi.createExchangeConnection({
        provider,
        label: connectionLabel || undefined,
        api_key: apiKey,
        api_secret: apiSecret,
        passphrase: passphrase || undefined,
        sandbox_mode: sandboxMode,
        can_trade: canTrade,
      });
      setConnectionLabel("");
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      setSandboxMode(false);
      setCanTrade(false);
      await loadSettings();
      void refreshAuthUser(); // sync AuthProvider (wallet_access may change)
      flash();
    } catch {
      setError("Unable to save this exchange connection.");
    } finally {
      setSavingConnection(false);
    }
  };

  const handleDeleteConnection = async (id: string) => {
    try {
      await authApi.deleteExchangeConnection(id);
      await loadSettings();
      flash();
    } catch {
      setError("Unable to delete this exchange connection.");
    }
  };

  const toggleNotif = (key: string, current: boolean, setter: (v: boolean) => void) => {
    setter(!current);
    localStorage.setItem(`gluetrade-notif-${key}`, String(!current));
    flash();
  };

  // Use local Settings state first (freshest after updateMe), fallback to AuthProvider
  const displayUser = user ?? authUser;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-2xl font-bold glow-text mb-1">Settings</h1>
        <p className="text-xs text-[var(--text-muted)]">
          Manage account access, legal acceptance, AI behaviour and private exchange connectivity.
        </p>
      </div>

      {saved && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl bg-[var(--page-accent)]/15 px-4 py-2 text-sm font-medium accent-text">
          <Check className="h-4 w-4" /> Saved
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-[#ef4444]/20 bg-[#ef4444]/8 px-4 py-3 text-sm text-[#ef4444]">
          {error}
        </div>
      )}

      <SettingSection title="Profile" icon={User}>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-[13px] text-[var(--text-muted)]">Username</label>
            <div className="rounded-xl px-3 py-2 text-[15px] text-[var(--foreground)] border border-[var(--glass-border)] bg-[var(--glass-bg)]">
              {displayUser?.username || "\u2014"}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[13px] text-[var(--text-muted)]">Email</label>
            <div className="rounded-xl px-3 py-2 text-[15px] text-[var(--text-secondary)] border border-[var(--glass-border)] bg-[var(--glass-bg)]">
              {displayUser?.email || "\u2014"}
            </div>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Access & Billing" icon={Shield}>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-3">
            <p className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">Plan</p>
            <p className="mt-1 text-[16px] font-semibold text-[var(--foreground)]">
              {(user?.subscription_plan ?? "starter").toUpperCase()}
            </p>
          </div>
          <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-3">
            <p className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">Status</p>
            <p className="mt-1 text-[16px] font-semibold text-[var(--foreground)]">
              {(user?.subscription_status ?? "trial").replace("_", " ")}
            </p>
          </div>
          <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-3">
            <p className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">Wallet Access</p>
            <p
              className={cn(
                "mt-1 text-[16px] font-semibold",
                user?.wallet_access_enabled ? "text-[#22c55e]" : "text-[var(--foreground)]",
              )}
            >
              {user?.wallet_access_enabled ? "Unlocked" : "Locked"}
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3">
          <p className="text-[13px] text-[var(--text-secondary)]">
            {user?.wallet_access_reason ??
              "Wallet features unlock when terms are accepted, the subscription is active, and at least one exchange is connected."}
          </p>
          {!user?.accepted_terms_at && (
            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={() => void handleAcceptTerms()}
                className="rounded-xl px-3 py-2 text-sm font-medium accent-bg accent-text"
              >
                Accept Terms
              </button>
              <Link href="/terms" className="text-sm text-[var(--page-accent)] hover:underline">
                Read Terms & Conditions
              </Link>
            </div>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Preferred Plan</p>
            <div className="space-y-2">
              {SUBSCRIPTION_PLANS.map((plan) => (
                <ChoiceCard
                  key={plan.id}
                  active={(user?.subscription_plan ?? "starter") === plan.id}
                  title={plan.label}
                  description={plan.desc}
                  onClick={() => void saveUserProfile({ subscription_plan: plan.id })}
                />
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Billing Preference</p>
            <div className="grid grid-cols-2 gap-2">
              {(["monthly", "yearly"] as const).map((cycle) => (
                <button
                  key={cycle}
                  onClick={() => void saveUserProfile({ billing_cycle: cycle })}
                  className={cn(
                    "rounded-xl border px-4 py-3 text-sm font-medium transition-all",
                    (user?.billing_cycle ?? "monthly") === cycle
                      ? "accent-bg accent-text"
                      : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]",
                  )}
                  style={{ borderColor: "var(--glass-border)" }}
                >
                  {cycle === "monthly" ? "Monthly" : "Yearly"}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[12px] text-[var(--text-muted)]">
              Billing workflow can be layered on top of this preference later without changing the user contract.
            </p>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="AI Behaviour" icon={Bot}>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Behaviour Style</p>
            <div className="space-y-2">
              {AI_BEHAVIOR_OPTIONS.map((item) => (
                <ChoiceCard
                  key={item.id}
                  active={(user?.ai_behavior_style ?? "balanced") === item.id}
                  title={item.label}
                  description={item.desc}
                  onClick={() => void saveUserProfile({ ai_behavior_style: item.id })}
                />
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Assistant Tone</p>
            <div className="space-y-2">
              {AI_TONE_OPTIONS.map((item) => (
                <ChoiceCard
                  key={item.id}
                  active={(user?.ai_assistant_tone ?? "analytical") === item.id}
                  title={item.label}
                  description={item.desc}
                  onClick={() => void saveUserProfile({ ai_assistant_tone: item.id })}
                />
              ))}
            </div>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Trading Preferences" icon={Shield}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[15px] text-[var(--text-secondary)]">Trading Mode</span>
          <button
            onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
            className={cn(
              "flex items-center gap-2 rounded-xl px-3 py-1.5 text-[14px] font-medium transition-all",
              tradingMode === "auto" ? "bg-[#22c55e]/12 text-[#22c55e]" : "",
            )}
            style={{
              background: tradingMode === "auto" ? undefined : "var(--glass-bg)",
              border: "1px solid var(--glass-border)",
            }}
          >
            {tradingMode === "auto" ? <Bot className="h-3.5 w-3.5" /> : <Hand className="h-3.5 w-3.5" />}
            <span>{tradingMode === "auto" ? "Auto (AI)" : "Manual"}</span>
          </button>
        </div>

        <div>
          <label className="text-[13px] text-[var(--text-muted)] mb-2 block">Risk Profile</label>
          <div className="space-y-2">
            {RISK_PROFILES.map((item) => (
              <ChoiceCard
                key={item.id}
                active={riskProfile === item.id}
                title={item.label}
                description={item.desc}
                onClick={() => void saveRiskProfile(item.id)}
              />
            ))}
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Exchange Connections" icon={Key}>
        <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3">
          <p className="text-[14px] font-medium text-[var(--foreground)]">
            Connect your own exchange credentials
          </p>
          <p className="mt-1 text-[13px] text-[var(--text-muted)]">
            The app adds the intelligence layer on top of your own exchange account. By default, wallet balances,
            holdings and live execution stay locked until at least one private connection is configured.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <form onSubmit={handleCreateConnection} autoComplete="off" className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-[13px] text-[var(--text-muted)]">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 text-[15px] text-[var(--foreground)]"
                >
                  {providers.map((item) => (
                    <option key={item.provider} value={item.provider}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[13px] text-[var(--text-muted)]">Label</label>
                <input
                  value={connectionLabel}
                  onChange={(e) => setConnectionLabel(e.target.value)}
                  placeholder="Main account"
                  className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 text-[15px] text-[var(--foreground)]"
                />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-[13px] text-[var(--text-muted)]">API Key</label>
                <input
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  required
                  autoComplete="off"
                  className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 text-[15px] text-[var(--foreground)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[13px] text-[var(--text-muted)]">API Secret</label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  required
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 text-[15px] text-[var(--foreground)]"
                />
              </div>
            </div>

            {selectedProvider?.requires_passphrase && (
              <div>
                <label className="mb-1 block text-[13px] text-[var(--text-muted)]">Passphrase</label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  autoComplete="new-password"
                  className="w-full rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 text-[15px] text-[var(--foreground)]"
                />
              </div>
            )}

            <div className="grid gap-3 md:grid-cols-2">
              <Toggle enabled={sandboxMode} onChange={() => setSandboxMode((current) => !current)} label="Use sandbox / testnet" />
              <Toggle enabled={canTrade} onChange={() => setCanTrade((current) => !current)} label="Allow live trading from app" />
            </div>

            <button
              type="submit"
              disabled={savingConnection || !apiKey || !apiSecret}
              className="rounded-xl px-4 py-2 text-sm font-medium accent-bg accent-text disabled:opacity-50"
            >
              {savingConnection ? "Saving..." : "Save Connection"}
            </button>
          </form>

          <div className="space-y-3">
            <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3">
              <p className="text-[14px] font-medium text-[var(--foreground)]">
                {selectedProvider?.label ?? "Provider"} setup help
              </p>
              <div className="mt-3 space-y-2">
                {(selectedProvider?.setup_steps ?? []).map((step) => (
                  <p key={step} className="text-[13px] text-[var(--text-muted)]">
                    • {step}
                  </p>
                ))}
              </div>
              <div className="mt-3">
                <p className="text-[12px] uppercase tracking-wider text-[var(--text-muted)]">
                  Recommended permissions
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(selectedProvider?.recommended_permissions ?? []).map((item) => (
                    <span
                      key={item}
                      className="rounded-full border border-[var(--glass-border)] bg-[var(--glass-bg)] px-2 py-1 text-[12px] text-[var(--text-secondary)]"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3">
              <p className="text-[14px] font-medium text-[var(--foreground)]">Connected accounts</p>
              <div className="mt-3 space-y-2">
                {connections.length === 0 ? (
                  <p className="text-[13px] text-[var(--text-muted)]">
                    No private exchange connection saved yet.
                  </p>
                ) : (
                  connections.map((connection) => (
                    <div
                      key={connection.id}
                      className="rounded-xl border border-[var(--glass-border)] bg-[var(--background)]/40 px-3 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[14px] font-semibold text-[var(--foreground)]">
                            {connection.label} · {connection.provider}
                          </p>
                          <p className="mt-1 text-[12px] text-[var(--text-muted)]">
                            {connection.api_key_hint} · {connection.can_trade ? "Trading enabled" : "Read-only"}
                            {connection.sandbox_mode ? " · Sandbox" : ""}
                          </p>
                        </div>
                        <button
                          onClick={() => void handleDeleteConnection(connection.id)}
                          className="text-[12px] font-medium text-[#ef4444]"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Currency & Appearance" icon={Palette}>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Display Currency</p>
            <div className="grid grid-cols-3 gap-2">
              {(Object.entries(CURRENCIES) as [CurrencyCode, typeof CURRENCIES.usd][]).map(([code, info]) => (
                <button
                  key={code}
                  onClick={() => {
                    setCurrency(code);
                    flash();
                  }}
                  className={cn(
                    "rounded-xl py-2.5 text-center text-[14px] font-medium transition-all border",
                    currency === code
                      ? "accent-bg accent-text"
                      : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]",
                  )}
                  style={{ borderColor: "var(--glass-border)" }}
                >
                  <div className="text-base">{info.symbol}</div>
                  <div className="text-[12px] mt-0.5 opacity-70">{code.toUpperCase()}</div>
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[13px] text-[var(--text-muted)]">Theme</p>
            <button
              onClick={toggleTheme}
              className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-4 py-3 text-[14px] font-medium text-[var(--foreground)]"
            >
              {theme === "dark" ? "Dark" : "Light"}
            </button>
          </div>
        </div>
      </SettingSection>

      <SettingSection title="Notifications" icon={Bell}>
        <Toggle
          label="Email notifications"
          enabled={notifEmail}
          onChange={() => toggleNotif("email", notifEmail, setNotifEmail)}
        />
        <Toggle
          label="Push notifications"
          enabled={notifPush}
          onChange={() => toggleNotif("push", notifPush, setNotifPush)}
        />
        <Toggle
          label="Telegram alerts"
          enabled={notifTelegram}
          onChange={() => toggleNotif("telegram", notifTelegram, setNotifTelegram)}
        />
      </SettingSection>

      <div className="liquid-glass-card p-5 border-[#ef4444]/20">
        <div className="flex items-center gap-2.5 mb-3">
          <Trash2 className="h-4.5 w-4.5 text-[#ef4444]" />
          <h2 className="text-sm font-semibold text-[#ef4444]">Zone de danger</h2>
        </div>

        {/* Data export (RGPD Art. 20) */}
        <div className="mb-4">
          <p className="text-[13px] text-[var(--text-muted)] mb-2">
            Exporter toutes vos donnees personnelles (RGPD Art. 20 — droit a la portabilite).
          </p>
          <button
            onClick={async () => {
              try {
                const data = await authApi.exportData();
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `gluetrade-data-export-${new Date().toISOString().slice(0, 10)}.json`;
                a.click();
                URL.revokeObjectURL(url);
              } catch { /* ignore */ }
            }}
            className="rounded-xl px-4 py-2 text-[13px] font-medium text-[var(--text-secondary)] border border-[var(--glass-border)] hover:bg-[var(--glass-bg)] transition-all"
          >
            Telecharger mes donnees
          </button>
        </div>

        {/* Account deletion (RGPD Art. 17) */}
        <p className="text-[13px] text-[var(--text-muted)] mb-2">
          Supprimer definitivement votre compte et toutes les donnees associees. Cette action est irreversible.
        </p>
        {!deleteConfirm ? (
          <button
            onClick={() => setDeleteConfirm(true)}
            className="rounded-xl px-4 py-2 text-[14px] font-medium text-[#ef4444] border border-[#ef4444]/20 hover:bg-[#ef4444]/8 transition-all"
          >
            Supprimer mon compte
          </button>
        ) : (
          <div className="rounded-xl border border-[#ef4444]/30 bg-[#ef4444]/5 p-4 space-y-3">
            <p className="text-[13px] font-semibold text-[#ef4444]">
              Confirmez la suppression en saisissant votre mot de passe :
            </p>
            <input
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder="Votre mot de passe"
              className="w-full rounded-lg border border-[#ef4444]/20 bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] outline-none"
            />
            {deleteError && <p className="text-[12px] text-[#ef4444]">{deleteError}</p>}
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  if (!deletePassword) return;
                  setDeleteError("");
                  try {
                    await authApi.deleteAccount(deletePassword);
                    localStorage.clear();
                    window.location.href = "/login";
                  } catch (err: unknown) {
                    setDeleteError(err instanceof Error ? err.message : "Echec de la suppression.");
                  }
                }}
                disabled={!deletePassword}
                className="rounded-lg px-4 py-2 text-[13px] font-semibold bg-[#ef4444] text-white hover:bg-[#dc2626] transition-all disabled:opacity-40"
              >
                Confirmer la suppression
              </button>
              <button
                onClick={() => { setDeleteConfirm(false); setDeletePassword(""); setDeleteError(""); }}
                className="rounded-lg px-4 py-2 text-[13px] text-[var(--text-muted)] hover:bg-[var(--glass-bg)] transition-all"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>

      {loading && (
        <p className="text-xs text-[var(--text-muted)]">
          Loading account settings…
        </p>
      )}
    </div>
  );
}
