"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8042";

interface TierConfig {
  name: string;
  price: number;
  price_label: string;
  messages_per_day: number;
  memory_slots: number;
  voice_per_day: number;
  image_per_day: number;
  proactive_messages: boolean;
  priority_response: boolean;
  export_memories: boolean;
  group_mode: boolean;
}

interface UsageData {
  tier: string;
  status: string;
  messages_today: number;
  messages_limit: number;
  voice_today: number;
  voice_limit: number;
  image_today: number;
  image_limit: number;
  date: string;
}

const TIER_ORDER = ["free", "plus", "pro"];
const TIER_EMOJI: Record<string, string> = { free: "🆓", plus: "⭐", pro: "🚀" };

const FEATURES = [
  { key: "messages_per_day", label: "Messages / day" },
  { key: "memory_slots", label: "Memory slots" },
  { key: "voice_per_day", label: "Voice / day" },
  { key: "image_per_day", label: "Images / day" },
  { key: "proactive_messages", label: "Proactive messages" },
  { key: "priority_response", label: "Priority response" },
  { key: "export_memories", label: "Export memories" },
  { key: "group_mode", label: "Group mode" },
];

function formatValue(v: number | boolean): string {
  if (typeof v === "boolean") return v ? "✅" : "—";
  return v === -1 ? "Unlimited" : `${v}`;
}

function formatLimit(current: number, limit: number): string {
  return limit === -1 ? `${current} / ∞` : `${current} / ${limit}`;
}

export default function SubscriptionPage() {
  const [tiers, setTiers] = useState<Record<string, TierConfig>>({});
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [currentTier, setCurrentTier] = useState("free");
  const [loading, setLoading] = useState(true);

  const getUserId = () => {
    if (typeof window === "undefined") return "anon";
    return localStorage.getItem("nobi_user_id") || "anon";
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const userId = getUserId();
        const [tiersRes, usageRes] = await Promise.all([
          fetch(`${API_BASE}/api/tiers`),
          fetch(`${API_BASE}/api/usage?user_id=${userId}`),
        ]);
        if (tiersRes.ok) setTiers((await tiersRes.json()).tiers);
        if (usageRes.ok) setUsage((await usageRes.json()).usage);
      } catch {} finally { setLoading(false); }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-nori-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-center mb-1">✨ Nori Subscription</h1>
      <p className="text-center text-gray-400 mb-8">Choose the plan that fits you</p>

      {/* Usage Stats */}
      {usage && (
        <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5 mb-8">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">
            📊 Today&apos;s Usage — {usage.tier.charAt(0).toUpperCase() + usage.tier.slice(1)} Plan
          </h3>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="text-gray-300">💬 Messages: <span className="font-bold text-white">{formatLimit(usage.messages_today, usage.messages_limit)}</span></div>
            <div className="text-gray-300">🎤 Voice: <span className="font-bold text-white">{formatLimit(usage.voice_today, usage.voice_limit)}</span></div>
            <div className="text-gray-300">📷 Images: <span className="font-bold text-white">{formatLimit(usage.image_today, usage.image_limit)}</span></div>
          </div>
        </div>
      )}

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {TIER_ORDER.map((tierKey) => {
          const tier = tiers[tierKey];
          if (!tier) return null;
          const isCurrent = tierKey === currentTier;
          const isPopular = tierKey === "plus";

          return (
            <div
              key={tierKey}
              className={`relative rounded-xl p-6 transition-all ${
                isPopular
                  ? "border-2 border-nori-500 bg-nori-500/10 shadow-lg shadow-nori-500/10"
                  : isCurrent
                  ? "border border-nori-400/30 bg-nori-500/5"
                  : "border border-gray-700 bg-gray-800/50"
              }`}
            >
              {isPopular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-nori-500 text-white text-xs px-4 py-1 rounded-full font-medium">
                  Most Popular
                </div>
              )}

              <div className="mb-4">
                <h2 className="text-lg font-semibold text-white">
                  {TIER_EMOJI[tierKey]} {tier.name}
                </h2>
                <p className="text-2xl font-bold text-white mt-1">{tier.price_label}</p>
              </div>

              <ul className="space-y-2 mb-6">
                {FEATURES.map((f) => {
                  const val = (tier as any)[f.key];
                  const display = formatValue(val);
                  const isEnabled = display !== "—";
                  return (
                    <li key={f.key} className="flex justify-between text-sm py-1 border-b border-gray-700/50">
                      <span className={isEnabled ? "text-gray-300" : "text-gray-500"}>{f.label}</span>
                      <span className={`font-medium ${isEnabled ? "text-white" : "text-gray-500"}`}>{display}</span>
                    </li>
                  );
                })}
              </ul>

              {isCurrent ? (
                <button
                  disabled
                  className="w-full py-2.5 rounded-lg bg-gray-700 text-gray-300 text-sm font-medium cursor-default"
                >
                  Current Plan ✓
                </button>
              ) : tierKey !== "free" ? (
                <button
                  className={`w-full py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isPopular
                      ? "bg-nori-500 hover:bg-nori-600 text-white"
                      : "bg-gray-700 hover:bg-gray-600 text-white"
                  }`}
                >
                  Subscribe to {tier.name}
                </button>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="text-center text-gray-500 text-xs mt-8">
        Payments powered by Stripe. Cancel anytime. Questions? Use /support on Telegram or visit our Support page.
      </p>
    </div>
  );
}
