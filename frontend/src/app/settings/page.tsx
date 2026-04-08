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
import { authApi, riskApi, smsApi } from "@/lib/api";
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
  Loader2,
  MessageSquare,
  Palette,
  Phone,
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

  // Backend-persisted notification preferences (under preferences.notifications)
  const [notifEmailEnabled, setNotifEmailEnabled] = useState(true);
  const [notifTrades, setNotifTrades] = useState(true);
  const [notifSecurity, setNotifSecurity] = useState(true);
  const [notifDeposits, setNotifDeposits] = useState(true);
  const [notifDailyRecap, setNotifDailyRecap] = useState(true);
  const [notifWeeklyRecap, setNotifWeeklyRecap] = useState(true);
  const [notifStrongSignals, setNotifStrongSignals] = useState(false);
  const [dailyRecapHour, setDailyRecapHour] = useState(8);
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
      // Hydrate notification toggles from backend preferences
      const notif = meResult.value.preferences?.notifications;
      if (notif) {
        setNotifEmailEnabled(notif.email_enabled !== false);
        setNotifTrades(notif.email_trades !== false);
        setNotifSecurity(notif.email_security !== false);
        setNotifDeposits(notif.email_deposits !== false);
        setNotifDailyRecap(notif.email_daily_recap !== false);
        setNotifWeeklyRecap(notif.email_weekly_recap !== false);
        setNotifStrongSignals(notif.email_strong_signals === true);
        if (typeof notif.daily_recap_hour === "number") {
          setDailyRecapHour(notif.daily_recap_hour);
        }
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

  const persistNotificationPrefs = async (
    overrides: Partial<{
      email_enabled: boolean;
      email_trades: boolean;
      email_security: boolean;
      email_deposits: boolean;
      email_daily_recap: boolean;
      email_weekly_recap: boolean;
      email_strong_signals: boolean;
      daily_recap_hour: number;
    }>,
  ) => {
    try {
      const next = await authApi.updateMe({
        preferences: {
          notifications: {
            email_enabled: notifEmailEnabled,
            email_trades: notifTrades,
            email_security: notifSecurity,
            email_deposits: notifDeposits,
            email_daily_recap: notifDailyRecap,
            email_weekly_recap: notifWeeklyRecap,
            email_strong_signals: notifStrongSignals,
            daily_recap_hour: dailyRecapHour,
            ...overrides,
          },
        },
      });
      setUser(next);
      flash();
    } catch {
      setError("Unable to save notification preferences.");
    }
  };

  const toggleBackendNotif = (
    key:
      | "email_enabled"
      | "email_trades"
      | "email_security"
      | "email_deposits"
      | "email_daily_recap"
      | "email_weekly_recap"
      | "email_strong_signals",
    current: boolean,
    setter: (v: boolean) => void,
  ) => {
    const next = !current;
    setter(next);
    void persistNotificationPrefs({ [key]: next });
  };

  // Use local Settings state first (freshest after updateMe), fallback to AuthProvider
  const displayUser = user ?? authUser;

  return (
    <div className="w-full max-w-[1520px] space-y-5">
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

      <SettingSection title="Notifications email" icon={Bell}>
        <p className="mb-3 text-[12px] text-[var(--text-muted)]">
          Selectionnez les emails que vous souhaitez recevoir. Le toggle principal coupe tous les emails en un clic.
        </p>
        <Toggle
          label="Activer les emails"
          enabled={notifEmailEnabled}
          onChange={() => toggleBackendNotif("email_enabled", notifEmailEnabled, setNotifEmailEnabled)}
        />
        <Toggle
          label="Confirmation des trades (achat / vente)"
          enabled={notifTrades}
          onChange={() => toggleBackendNotif("email_trades", notifTrades, setNotifTrades)}
        />
        <Toggle
          label="Alertes de securite (nouvelle connexion, IP)"
          enabled={notifSecurity}
          onChange={() => toggleBackendNotif("email_security", notifSecurity, setNotifSecurity)}
        />
        <Toggle
          label="Mouvements fiat (depots / retraits)"
          enabled={notifDeposits}
          onChange={() => toggleBackendNotif("email_deposits", notifDeposits, setNotifDeposits)}
        />
        <Toggle
          label="Recap quotidien IA (analyse + conseils)"
          enabled={notifDailyRecap}
          onChange={() => toggleBackendNotif("email_daily_recap", notifDailyRecap, setNotifDailyRecap)}
        />
        <Toggle
          label="Recap hebdomadaire (dimanche soir)"
          enabled={notifWeeklyRecap}
          onChange={() => toggleBackendNotif("email_weekly_recap", notifWeeklyRecap, setNotifWeeklyRecap)}
        />
        <Toggle
          label="Signaux IA tres forts (HIGH_CONVICTION)"
          enabled={notifStrongSignals}
          onChange={() => toggleBackendNotif("email_strong_signals", notifStrongSignals, setNotifStrongSignals)}
        />
        <div className="mt-3 pt-3 border-t border-[var(--glass-border)]">
          <label className="block text-[13px] text-[var(--text-secondary)] mb-2">
            Heure du recap quotidien : <span className="accent-text font-semibold">{String(dailyRecapHour).padStart(2, "0")}:00</span>
          </label>
          <input
            type="range"
            min={0}
            max={23}
            value={dailyRecapHour}
            onChange={(e) => setDailyRecapHour(Number(e.target.value))}
            onMouseUp={(e) =>
              void persistNotificationPrefs({
                daily_recap_hour: Number((e.target as HTMLInputElement).value),
              })
            }
            onTouchEnd={(e) =>
              void persistNotificationPrefs({
                daily_recap_hour: Number((e.target as HTMLInputElement).value),
              })
            }
            className="w-full"
          />
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
            Heure locale ({user?.timezone || "Europe/Paris"})
          </p>
        </div>

        <div className="mt-4 pt-3 border-t border-[var(--glass-border)]">
          <p className="mb-2 text-[12px] text-[var(--text-muted)]">Autres canaux (locaux a cet appareil)</p>
          <Toggle
            label="Notifications push (navigateur)"
            enabled={notifPush}
            onChange={() => toggleNotif("push", notifPush, setNotifPush)}
          />
          <Toggle
            label="Alertes Telegram"
            enabled={notifTelegram}
            onChange={() => toggleNotif("telegram", notifTelegram, setNotifTelegram)}
          />
          <Toggle
            label="Notifications email (legacy local)"
            enabled={notifEmail}
            onChange={() => toggleNotif("email", notifEmail, setNotifEmail)}
          />
        </div>
      </SettingSection>

      <SmsNotificationsSection />

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

// ---------------------------------------------------------------------------
// SMS notifications section
// ---------------------------------------------------------------------------

const SMS_EVENT_CATALOG: Array<{ key: string; label: string; group: string; defaultOn: boolean }> = [
  { key: "trade_buy", label: "Achat execute", group: "Trades", defaultOn: true },
  { key: "trade_sell", label: "Vente executee", group: "Trades", defaultOn: true },
  { key: "trade_failed", label: "Ordre echec", group: "Trades", defaultOn: false },
  { key: "stop_loss_hit", label: "Stop-loss declenche", group: "Trades", defaultOn: true },
  { key: "take_profit_hit", label: "Take-profit atteint", group: "Trades", defaultOn: false },
  { key: "circuit_breaker", label: "Circuit breaker", group: "Securite", defaultOn: true },
  { key: "emergency_halt", label: "Arret d'urgence", group: "Securite", defaultOn: true },
  { key: "heartbeat_miss", label: "Heartbeat manquant", group: "Securite", defaultOn: false },
  { key: "new_login_unknown", label: "Nouvelle IP de connexion", group: "Securite", defaultOn: false },
  { key: "api_key_error", label: "Erreur cle API Binance", group: "Securite", defaultOn: false },
  { key: "daily_recap", label: "Recap quotidien", group: "Recaps", defaultOn: true },
  { key: "pnl_milestone", label: "Seuil P&L atteint", group: "Recaps", defaultOn: false },
  { key: "position_opened_large", label: "Position importante ouverte", group: "Trades", defaultOn: false },
  { key: "auto_armed", label: "Auto-trading arme", group: "Auto", defaultOn: false },
  { key: "auto_disarmed", label: "Auto-trading desarme", group: "Auto", defaultOn: false },
];

function SmsNotificationsSection() {
  const [phoneInput, setPhoneInput] = useState("");
  const [code, setCode] = useState("");
  const [phoneNumber, setPhoneNumber] = useState<string | null>(null);
  const [phoneVerified, setPhoneVerified] = useState(false);
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [events, setEvents] = useState<Record<string, boolean>>({});
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [checkingCode, setCheckingCode] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const prefs = await smsApi.getPreferences();
        setPhoneNumber(prefs.phone_number);
        setPhoneVerified(prefs.phone_verified);
        setPhoneInput(prefs.phone_number || "");
        setSmsEnabled(prefs.sms.master_enabled);
        const merged: Record<string, boolean> = {};
        for (const item of SMS_EVENT_CATALOG) {
          merged[item.key] =
            prefs.sms.events[item.key] !== undefined
              ? Boolean(prefs.sms.events[item.key])
              : item.defaultOn;
        }
        setEvents(merged);
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Impossible de charger les preferences SMS");
      }
    })();
  }, []);

  const savePreferences = async (
    nextMaster: boolean,
    nextEvents: Record<string, boolean>,
  ) => {
    setLoading(true);
    setStatus(null);
    try {
      await smsApi.updatePreferences({
        master_enabled: nextMaster,
        events: nextEvents,
      });
      setStatus("Preferences enregistrees");
      setTimeout(() => setStatus(null), 2000);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Echec de l'enregistrement");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleMaster = async () => {
    const next = !smsEnabled;
    setSmsEnabled(next);
    await savePreferences(next, events);
  };

  const handleToggleEvent = async (key: string) => {
    const next = { ...events, [key]: !events[key] };
    setEvents(next);
    await savePreferences(smsEnabled, next);
  };

  const handleSendCode = async () => {
    setStatus(null);
    setSendingCode(true);
    try {
      await smsApi.startVerification(phoneInput);
      setStatus("Code envoye par SMS");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Echec envoi code");
    } finally {
      setSendingCode(false);
    }
  };

  const handleCheckCode = async () => {
    setStatus(null);
    setCheckingCode(true);
    try {
      const result = await smsApi.checkVerification(phoneInput, code);
      if (result.verified) {
        setPhoneNumber(phoneInput);
        setPhoneVerified(true);
        setStatus("Numero verifie avec succes");
        setCode("");
      } else {
        setStatus("Code incorrect");
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Echec verification");
    } finally {
      setCheckingCode(false);
    }
  };

  const handleSendTest = async () => {
    setStatus(null);
    try {
      const result = await smsApi.sendTest();
      if (result.ok) {
        setStatus(`SMS test envoye (sid ${result.sid || "?"})`);
      } else {
        setStatus(result.error || "Echec envoi test");
      }
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Echec envoi test");
    }
  };

  const groupedEvents = SMS_EVENT_CATALOG.reduce<Record<string, typeof SMS_EVENT_CATALOG>>((acc, item) => {
    (acc[item.group] ??= []).push(item);
    return acc;
  }, {});

  return (
    <SettingSection title="Notifications SMS" icon={MessageSquare}>
      <p className="mb-3 text-[12px] text-[var(--text-muted)]">
        Recevez des alertes SMS sur votre telephone pour les trades et les evenements critiques.
        Activez au minimum les notifications de securite.
      </p>

      {/* Phone number + verification */}
      <div className="mb-4 rounded-xl border border-[var(--glass-border)] p-3" style={{ background: "var(--glass-bg)" }}>
        <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
          Numero de telephone (format international)
        </label>
        <div className="flex gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-lg border border-[var(--glass-border)] px-3 py-2" style={{ background: "var(--surface)" }}>
            <Phone className="h-3.5 w-3.5 text-[var(--text-muted)]" />
            <input
              type="tel"
              value={phoneInput}
              onChange={(e) => setPhoneInput(e.target.value)}
              placeholder="+33612345678"
              className="flex-1 bg-transparent text-[13px] text-[var(--foreground)] outline-none"
              disabled={sendingCode || checkingCode}
            />
            {phoneVerified && phoneNumber === phoneInput && (
              <span className="flex items-center gap-0.5 rounded-full bg-[var(--success)]/15 px-2 py-0.5 text-[9px] font-bold uppercase text-[var(--success)]">
                <Check className="h-3 w-3" /> Verifie
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleSendCode}
            disabled={sendingCode || !phoneInput}
            className="rounded-lg bg-[var(--page-accent)]/15 px-3 py-2 text-[11px] font-semibold text-[var(--page-accent)] disabled:opacity-40"
          >
            {sendingCode ? <Loader2 className="h-3 w-3 animate-spin" /> : "Envoyer code"}
          </button>
        </div>

        <div className="mt-2 flex gap-2">
          <input
            type="text"
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 10))}
            placeholder="Code (6 chiffres)"
            className="flex-1 rounded-lg border border-[var(--glass-border)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none"
            style={{ background: "var(--surface)" }}
            disabled={checkingCode}
          />
          <button
            type="button"
            onClick={handleCheckCode}
            disabled={checkingCode || !code}
            className="rounded-lg bg-[var(--success)]/15 px-3 py-2 text-[11px] font-semibold text-[var(--success)] disabled:opacity-40"
          >
            {checkingCode ? <Loader2 className="h-3 w-3 animate-spin" /> : "Verifier"}
          </button>
        </div>

        {phoneVerified && phoneNumber && (
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={handleSendTest}
              className="rounded-lg border border-[var(--glass-border)] px-2.5 py-1 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]"
            >
              Envoyer SMS test
            </button>
          </div>
        )}
        {status && <p className="mt-2 text-[10px] text-[var(--text-muted)]">{status}</p>}
      </div>

      {/* Master toggle */}
      <Toggle
        label="Activer les notifications SMS"
        enabled={smsEnabled && phoneVerified}
        onChange={handleToggleMaster}
      />
      {!phoneVerified && (
        <p className="mb-3 text-[10px] italic text-[var(--text-muted)]">
          Verifiez d'abord votre numero pour activer les notifications.
        </p>
      )}

      {/* Granular toggles by group */}
      {phoneVerified && (
        <div className="mt-3 space-y-3">
          {Object.entries(groupedEvents).map(([group, items]) => (
            <div key={group}>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                {group}
              </p>
              <div className="grid grid-cols-1 gap-1">
                {items.map((item) => (
                  <Toggle
                    key={item.key}
                    label={item.label}
                    enabled={Boolean(events[item.key])}
                    onChange={() => void handleToggleEvent(item.key)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {loading && (
        <p className="mt-2 text-[10px] text-[var(--text-muted)]">Enregistrement...</p>
      )}
    </SettingSection>
  );
}
