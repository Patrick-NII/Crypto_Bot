"use client";

import { useState, useEffect } from "react";
import { usePageAccent } from "@/components/providers/theme-provider";
import { useTheme } from "@/components/providers/theme-provider";
import { useCurrency, CURRENCIES, type CurrencyCode } from "@/components/providers/currency-provider";
import { cn } from "@/lib/utils";
import {
  User, Globe, Palette, Shield, Bell, Key, Trash2, Sun, Moon, Bot, Hand, Check,
} from "lucide-react";

const RISK_PROFILES = [
  { id: "conservative", label: "Conservative", desc: "Lower risk, lower returns. Max 5% per trade." },
  { id: "moderate", label: "Moderate", desc: "Balanced risk/reward. Max 10% per trade." },
  { id: "aggressive", label: "Aggressive", desc: "Higher risk, higher potential. Max 20% per trade." },
] as const;

function SettingSection({ title, icon: Icon, children }: { title: string; icon: typeof User; children: React.ReactNode }) {
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

function Toggle({ enabled, onChange, label }: { enabled: boolean; onChange: () => void; label: string }) {
  return (
    <button onClick={onChange} className="flex w-full items-center justify-between py-1.5">
      <span className="text-[13px] text-[var(--text-secondary)]">{label}</span>
      <div className={cn("w-9 h-5 rounded-full relative transition-colors", enabled ? "bg-[var(--page-accent)]" : "bg-[var(--glass-border)]")}>
        <div className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform", enabled ? "translate-x-4" : "translate-x-0.5")} />
      </div>
    </button>
  );
}

export default function SettingsPage() {
  usePageAccent("#8b5cf6", "139,92,246"); // Violet for settings

  const { theme, toggleTheme, tradingMode, setTradingMode } = useTheme();
  const { currency, setCurrency } = useCurrency();

  const [riskProfile, setRiskProfile] = useState("moderate");
  const [notifEmail, setNotifEmail] = useState(true);
  const [notifPush, setNotifPush] = useState(false);
  const [notifTelegram, setNotifTelegram] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("okamoey-risk-profile");
    if (saved) setRiskProfile(saved);
    setNotifEmail(localStorage.getItem("okamoey-notif-email") !== "false");
    setNotifPush(localStorage.getItem("okamoey-notif-push") === "true");
    setNotifTelegram(localStorage.getItem("okamoey-notif-telegram") === "true");
  }, []);

  const saveRiskProfile = (id: string) => {
    setRiskProfile(id);
    localStorage.setItem("okamoey-risk-profile", id);
    flash();
  };

  const toggleNotif = (key: string, current: boolean, setter: (v: boolean) => void) => {
    setter(!current);
    localStorage.setItem(`okamoey-notif-${key}`, String(!current));
    flash();
  };

  const flash = () => { setSaved(true); setTimeout(() => setSaved(false), 1500); };

  const demoUser = typeof window !== "undefined" ? JSON.parse(localStorage.getItem("demo_user") || '{"username":"DemoTrader","email":"demo@okamoey.com"}') : {};

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold glow-text mb-1">Settings</h1>
      <p className="text-xs text-[var(--text-muted)] mb-4">Preferences are saved automatically.</p>

      {/* Saved indicator */}
      {saved && (
        <div className="fixed top-4 right-4 z-50 flex items-center gap-2 rounded-xl bg-[var(--page-accent)]/15 px-4 py-2 text-sm font-medium accent-text animate-fade-in">
          <Check className="h-4 w-4" /> Saved
        </div>
      )}

      {/* Profile */}
      <SettingSection title="Profile" icon={User}>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Username</label>
            <div className="rounded-xl px-3 py-2 text-[13px] text-[var(--foreground)]" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
              {demoUser.username || "DemoTrader"}
            </div>
          </div>
          <div>
            <label className="text-[11px] text-[var(--text-muted)] mb-1 block">Email</label>
            <div className="rounded-xl px-3 py-2 text-[13px] text-[var(--text-secondary)]" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
              {demoUser.email || "demo@okamoey.com"}
            </div>
          </div>
        </div>
      </SettingSection>

      {/* Currency */}
      <SettingSection title="Currency" icon={Globe}>
        <div className="grid grid-cols-5 gap-2">
          {(Object.entries(CURRENCIES) as [CurrencyCode, typeof CURRENCIES.usd][]).map(([code, info]) => (
            <button
              key={code}
              onClick={() => { setCurrency(code); flash(); }}
              className={cn(
                "rounded-xl py-2.5 text-center text-[12px] font-medium transition-all",
                currency === code
                  ? "accent-bg accent-text ring-1 ring-[var(--page-accent)]/40"
                  : "text-[var(--text-secondary)] hover:bg-[var(--glass-bg)]",
              )}
              style={{ border: "1px solid var(--glass-border)" }}
            >
              <div className="text-base">{info.symbol}</div>
              <div className="text-[10px] mt-0.5 opacity-70">{code.toUpperCase()}</div>
            </button>
          ))}
        </div>
      </SettingSection>

      {/* Appearance */}
      <SettingSection title="Appearance" icon={Palette}>
        <div className="flex items-center justify-between">
          <span className="text-[13px] text-[var(--text-secondary)]">Theme</span>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-[12px] font-medium transition-all"
            style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}
          >
            {theme === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
            <span className="text-[var(--foreground)]">{theme === "dark" ? "Dark" : "Light"}</span>
          </button>
        </div>
      </SettingSection>

      {/* Trading */}
      <SettingSection title="Trading" icon={Shield}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[13px] text-[var(--text-secondary)]">Trading Mode</span>
          <button
            onClick={() => setTradingMode(tradingMode === "manual" ? "auto" : "manual")}
            className={cn(
              "flex items-center gap-2 rounded-xl px-3 py-1.5 text-[12px] font-medium transition-all",
              tradingMode === "auto" ? "bg-[#22c55e]/12 text-[#22c55e]" : "",
            )}
            style={{ background: tradingMode === "auto" ? undefined : "var(--glass-bg)", border: "1px solid var(--glass-border)" }}
          >
            {tradingMode === "auto" ? <Bot className="h-3.5 w-3.5" /> : <Hand className="h-3.5 w-3.5" />}
            <span>{tradingMode === "auto" ? "Auto (AI)" : "Manual"}</span>
          </button>
        </div>

        <div>
          <label className="text-[11px] text-[var(--text-muted)] mb-2 block">Risk Profile</label>
          <div className="space-y-1.5">
            {RISK_PROFILES.map((p) => (
              <button
                key={p.id}
                onClick={() => saveRiskProfile(p.id)}
                className={cn(
                  "w-full flex items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-all",
                  riskProfile === p.id ? "accent-bg" : "hover:bg-[var(--glass-bg)]",
                )}
                style={{ border: "1px solid var(--glass-border)" }}
              >
                <div className={cn("mt-0.5 h-4 w-4 rounded-full border-2 flex items-center justify-center transition-colors", riskProfile === p.id ? "border-[var(--page-accent)] bg-[var(--page-accent)]" : "border-[var(--glass-border)]")}>
                  {riskProfile === p.id && <Check className="h-2.5 w-2.5 text-white" />}
                </div>
                <div>
                  <p className={cn("text-[13px] font-medium", riskProfile === p.id ? "accent-text" : "text-[var(--foreground)]")}>{p.label}</p>
                  <p className="text-[11px] text-[var(--text-muted)]">{p.desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </SettingSection>

      {/* Notifications */}
      <SettingSection title="Notifications" icon={Bell}>
        <Toggle label="Email notifications" enabled={notifEmail} onChange={() => toggleNotif("email", notifEmail, setNotifEmail)} />
        <Toggle label="Push notifications" enabled={notifPush} onChange={() => toggleNotif("push", notifPush, setNotifPush)} />
        <Toggle label="Telegram alerts" enabled={notifTelegram} onChange={() => toggleNotif("telegram", notifTelegram, setNotifTelegram)} />
      </SettingSection>

      {/* API Keys */}
      <SettingSection title="API Keys" icon={Key}>
        <p className="text-[11px] text-[var(--text-muted)]">Connect your exchange accounts to enable live trading.</p>
        <div className="space-y-2">
          {["Binance", "Coinbase", "Kraken"].map((ex) => (
            <div key={ex} className="flex items-center justify-between rounded-xl px-3 py-2" style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
              <span className="text-[13px] text-[var(--foreground)]">{ex}</span>
              <span className="text-[11px] text-[var(--text-muted)]">Not connected</span>
            </div>
          ))}
        </div>
      </SettingSection>

      {/* Danger zone */}
      <div className="liquid-glass-card p-5 border-[#ef4444]/20">
        <div className="flex items-center gap-2.5 mb-3">
          <Trash2 className="h-4.5 w-4.5 text-[#ef4444]" />
          <h2 className="text-sm font-semibold text-[#ef4444]">Danger Zone</h2>
        </div>
        <p className="text-[11px] text-[var(--text-muted)] mb-3">Permanently delete your account and all data.</p>
        <button className="rounded-xl px-4 py-2 text-[12px] font-medium text-[#ef4444] border border-[#ef4444]/20 hover:bg-[#ef4444]/8 transition-all">
          Delete Account
        </button>
      </div>
    </div>
  );
}
