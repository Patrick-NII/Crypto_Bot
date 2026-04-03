"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Bell,
  BellRing,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Percent,
  Clock,
} from "lucide-react";
import { alertsApi } from "@/lib/api";
import type { Alert, AlertType, AlertChannel } from "@/lib/types";
import { formatCurrency, formatRelative, cn } from "@/lib/utils";
import { GlassCard } from "@/components/ui/glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-white/5", className)} />;
}

function alertTypeIcon(type: AlertType) {
  switch (type) {
    case "price_above":
      return <ArrowUp className="h-4 w-4 text-success" />;
    case "price_below":
      return <ArrowDown className="h-4 w-4 text-danger" />;
    case "pct_change":
      return <Percent className="h-4 w-4 text-warning" />;
  }
}

function alertTypeLabel(type: AlertType) {
  switch (type) {
    case "price_above":
      return "Price Above";
    case "price_below":
      return "Price Below";
    case "pct_change":
      return "% Change";
  }
}

function statusVariant(status: string) {
  switch (status) {
    case "active":
      return "success" as const;
    case "triggered":
      return "warning" as const;
    case "expired":
      return "default" as const;
    case "disabled":
      return "default" as const;
    default:
      return "default" as const;
  }
}

export default function AlertsPage() {
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  // Create form
  const [showForm, setShowForm] = useState(false);
  const [formSymbol, setFormSymbol] = useState("BTC");
  const [formType, setFormType] = useState<AlertType>("price_above");
  const [formValue, setFormValue] = useState("");
  const [formChannel, setFormChannel] = useState<AlertChannel>("push");
  const [creating, setCreating] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await alertsApi.list();
      setAlerts(data);
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    if (!formValue || isNaN(Number(formValue))) return;
    setCreating(true);
    try {
      await alertsApi.create({
        symbol: formSymbol,
        alert_type: formType,
        value: Number(formValue),
        channel: formChannel,
      });
      setFormValue("");
      setShowForm(false);
      fetchData();
    } catch {
      // handle
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await alertsApi.delete(id);
      fetchData();
    } catch {
      // handle
    }
  };

  const activeAlerts = alerts.filter((a) => a.status === "active");
  const triggeredAlerts = alerts.filter((a) => a.status === "triggered");
  const otherAlerts = alerts.filter(
    (a) => a.status !== "active" && a.status !== "triggered",
  );

  if (loading) {
    return (
      <div className="relative z-10 min-h-screen p-4 md:p-8">
        <h1 className="mb-8 text-3xl font-bold glow-text">Alerts</h1>
        <SkeletonBlock className="h-40" />
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="relative z-10 min-h-screen p-4 md:p-8">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold glow-text">Alerts</h1>
          <Badge variant="purple">{activeAlerts.length} active</Badge>
        </div>
        <Button onClick={() => setShowForm(!showForm)}>
          <Plus className="h-4 w-4" />
          Create Alert
        </Button>
      </div>

      {/* Create Alert Form */}
      {showForm && (
        <GlassCard className="mb-6">
          <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-white">
            <BellRing className="h-5 w-5 text-accent-purple" />
            New Alert
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {/* Symbol */}
            <div>
              <label className="mb-1 block text-xs text-white/40">Symbol</label>
              <select
                value={formSymbol}
                onChange={(e) => setFormSymbol(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              >
                {["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT"].map(
                  (s) => (
                    <option key={s} value={s} className="bg-[#0a0a1a]">
                      {s}
                    </option>
                  ),
                )}
              </select>
            </div>

            {/* Alert Type */}
            <div>
              <label className="mb-1 block text-xs text-white/40">
                Alert Type
              </label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value as AlertType)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              >
                <option value="price_above" className="bg-[#0a0a1a]">
                  Price Above
                </option>
                <option value="price_below" className="bg-[#0a0a1a]">
                  Price Below
                </option>
                <option value="pct_change" className="bg-[#0a0a1a]">
                  % Change
                </option>
              </select>
            </div>

            {/* Value */}
            <div>
              <label className="mb-1 block text-xs text-white/40">
                {formType === "pct_change" ? "Percentage" : "Price"}
              </label>
              <input
                type="number"
                value={formValue}
                onChange={(e) => setFormValue(e.target.value)}
                placeholder={formType === "pct_change" ? "5.0" : "50000"}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              />
            </div>

            {/* Channel */}
            <div>
              <label className="mb-1 block text-xs text-white/40">Channel</label>
              <select
                value={formChannel}
                onChange={(e) => setFormChannel(e.target.value as AlertChannel)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent-purple"
              >
                <option value="push" className="bg-[#0a0a1a]">
                  Push
                </option>
                <option value="email" className="bg-[#0a0a1a]">
                  Email
                </option>
                <option value="sms" className="bg-[#0a0a1a]">
                  SMS
                </option>
              </select>
            </div>

            {/* Submit */}
            <div className="flex items-end">
              <Button
                className="w-full"
                onClick={handleCreate}
                loading={creating}
                disabled={!formValue}
              >
                Create
              </Button>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Active Alerts */}
      <div className="mb-8">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <Bell className="h-5 w-5 text-success" />
          Active Alerts
        </h2>
        {activeAlerts.length === 0 ? (
          <GlassCard>
            <div className="flex flex-col items-center gap-3 py-8">
              <Bell className="h-10 w-10 text-white/10" />
              <p className="text-sm text-white/40">
                No active alerts. Create one to get started.
              </p>
            </div>
          </GlassCard>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {activeAlerts.map((alert) => (
              <GlassCard key={alert.id} hover className="flex flex-col">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {alertTypeIcon(alert.alert_type)}
                    <span className="text-lg font-bold text-white">
                      {alert.symbol}
                    </span>
                  </div>
                  <Badge variant={statusVariant(alert.status)}>
                    {alert.status}
                  </Badge>
                </div>

                <div className="mt-3 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Type</span>
                    <span className="text-white/70">
                      {alertTypeLabel(alert.alert_type)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Value</span>
                    <span className="font-mono text-white">
                      {alert.alert_type === "pct_change"
                        ? `${alert.value}%`
                        : formatCurrency(alert.value)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Channel</span>
                    <Badge variant="info">{alert.channel}</Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Created</span>
                    <span className="text-white/50">
                      {formatRelative(alert.created_at)}
                    </span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5">
                  <Button
                    size="sm"
                    variant="danger"
                    className="w-full"
                    onClick={() => handleDelete(alert.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                    Delete
                  </Button>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>

      {/* Recently Triggered */}
      {triggeredAlerts.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <BellRing className="h-5 w-5 text-warning" />
            Recently Triggered
          </h2>
          <GlassCard>
            <div className="space-y-3">
              {triggeredAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    {alertTypeIcon(alert.alert_type)}
                    <div>
                      <span className="font-semibold text-white">
                        {alert.symbol}
                      </span>
                      <span className="ml-2 text-xs text-white/40">
                        {alertTypeLabel(alert.alert_type)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-white/70">
                      {alert.alert_type === "pct_change"
                        ? `${alert.value}%`
                        : formatCurrency(alert.value)}
                    </span>
                    <div className="flex items-center gap-1 text-xs text-white/40">
                      <Clock className="h-3 w-3" />
                      {alert.triggered_at
                        ? formatRelative(alert.triggered_at)
                        : "N/A"}
                    </div>
                    <Badge variant="warning">triggered</Badge>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      )}

      {/* Expired / Disabled */}
      {otherAlerts.length > 0 && (
        <div>
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white/50">
            <Clock className="h-5 w-5 text-white/30" />
            Past Alerts
          </h2>
          <GlassCard>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-xs uppercase tracking-wider text-white/30">
                    <th className="pb-3 pr-3">Symbol</th>
                    <th className="pb-3 pr-3">Type</th>
                    <th className="pb-3 pr-3 text-right">Value</th>
                    <th className="pb-3 pr-3">Channel</th>
                    <th className="pb-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {otherAlerts.map((alert) => (
                    <tr
                      key={alert.id}
                      className="border-b border-white/5 text-white/40"
                    >
                      <td className="py-2 pr-3 font-semibold">
                        {alert.symbol}
                      </td>
                      <td className="py-2 pr-3">
                        {alertTypeLabel(alert.alert_type)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono">
                        {alert.alert_type === "pct_change"
                          ? `${alert.value}%`
                          : formatCurrency(alert.value)}
                      </td>
                      <td className="py-2 pr-3">{alert.channel}</td>
                      <td className="py-2">
                        <Badge variant="default">{alert.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
