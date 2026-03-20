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

const FEATURES: { key: string; label: string; format: (v: number | boolean) => string }[] = [
  { key: "messages_per_day", label: "Messages / day", format: (v) => v === -1 ? "Unlimited" : `${v}` },
  { key: "memory_slots", label: "Memory slots", format: (v) => v === -1 ? "Unlimited" : `${v}` },
  { key: "voice_per_day", label: "Voice messages / day", format: (v) => v === -1 ? "Unlimited" : `${v}` },
  { key: "image_per_day", label: "Image analysis / day", format: (v) => v === -1 ? "Unlimited" : `${v}` },
  { key: "proactive_messages", label: "Proactive messages", format: (v) => v ? "✅" : "❌" },
  { key: "priority_response", label: "Priority response", format: (v) => v ? "✅" : "❌" },
  { key: "export_memories", label: "Export memories", format: (v) => v ? "✅" : "❌" },
  { key: "group_mode", label: "Group mode", format: (v) => v ? "✅" : "❌" },
];

export default function SubscriptionPage() {
  const [tiers, setTiers] = useState<Record<string, TierConfig>>({});
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [currentTier, setCurrentTier] = useState("free");
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState<string | null>(null);

  // Get user ID from localStorage or URL params
  const getUserId = () => {
    if (typeof window === "undefined") return "anon";
    const params = new URLSearchParams(window.location.search);
    return params.get("user_id") || localStorage.getItem("nobi_user_id") || "anon";
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const userId = getUserId();

        const [tiersRes, usageRes, subRes] = await Promise.all([
          fetch(`${API_BASE}/api/tiers`),
          fetch(`${API_BASE}/api/usage?user_id=${userId}`),
          fetch(`${API_BASE}/api/subscription?user_id=${userId}`),
        ]);

        if (tiersRes.ok) {
          const data = await tiersRes.json();
          setTiers(data.tiers);
        }

        if (usageRes.ok) {
          const data = await usageRes.json();
          setUsage(data.usage);
        }

        if (subRes.ok) {
          const data = await subRes.json();
          setCurrentTier(data.subscription?.tier || "free");
        }
      } catch (err) {
        console.error("Failed to fetch subscription data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleSubscribe = async (tier: string) => {
    setSubscribing(tier);
    try {
      const userId = getUserId();
      const res = await fetch(`${API_BASE}/api/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          tier,
          success_url: `${window.location.origin}/subscription?success=true`,
          cancel_url: `${window.location.origin}/subscription?cancelled=true`,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) {
          window.location.href = data.checkout_url;
          return;
        }
      }

      const error = await res.json().catch(() => ({ detail: "Unknown error" }));
      alert(error.detail || "Failed to start checkout. Stripe may not be configured yet.");
    } catch (err) {
      alert("Failed to connect to the server. Please try again later.");
    } finally {
      setSubscribing(null);
    }
  };

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel your subscription?")) return;

    try {
      const userId = getUserId();
      const res = await fetch(`${API_BASE}/api/subscription/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });

      if (res.ok) {
        alert("Subscription cancelled. You'll keep access until the end of your billing period.");
        window.location.reload();
      } else {
        const error = await res.json().catch(() => ({ detail: "Failed to cancel" }));
        alert(error.detail);
      }
    } catch {
      alert("Failed to connect. Please try again.");
    }
  };

  const formatLimit = (current: number, limit: number) => {
    if (limit === -1) return `${current} / ∞`;
    return `${current} / ${limit}`;
  };

  const successParam = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("success") : null;
  const cancelledParam = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("cancelled") : null;

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1rem" }}>
      <h1 style={{ textAlign: "center", marginBottom: "0.5rem" }}>✨ Nori Subscription</h1>
      <p style={{ textAlign: "center", color: "#666", marginBottom: "1rem" }}>
        Unlock more of your AI companion
      </p>


      {successParam && (
        <div style={{ background: "#d4edda", color: "#155724", padding: "1rem", borderRadius: 8, marginBottom: "1rem", textAlign: "center" }}>
          🎉 Subscription activated! Welcome to the family!
        </div>
      )}

      {cancelledParam && (
        <div style={{ background: "#fff3cd", color: "#856404", padding: "1rem", borderRadius: 8, marginBottom: "1rem", textAlign: "center" }}>
          Checkout cancelled. No worries — you can subscribe anytime!
        </div>
      )}

      {/* Usage Stats */}
      {usage && (
        <div style={{ background: "#f8f9fa", borderRadius: 12, padding: "1.5rem", marginBottom: "2rem" }}>
          <h3 style={{ marginTop: 0 }}>📊 Today&apos;s Usage — {usage.tier.charAt(0).toUpperCase() + usage.tier.slice(1)} Plan</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
            <div>💬 Messages: <strong>{formatLimit(usage.messages_today, usage.messages_limit)}</strong></div>
            <div>🎤 Voice: <strong>{formatLimit(usage.voice_today, usage.voice_limit)}</strong></div>
            <div>📷 Images: <strong>{formatLimit(usage.image_today, usage.image_limit)}</strong></div>
          </div>
        </div>
      )}

      {/* Pricing Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "1.5rem", marginBottom: "2rem" }}>
        {TIER_ORDER.map((tierKey) => {
          const tier = tiers[tierKey];
          if (!tier) return null;
          const isCurrent = tierKey === currentTier;
          const isPopular = tierKey === "plus";

          return (
            <div
              key={tierKey}
              style={{
                border: isPopular ? "2px solid #6c63ff" : "1px solid #ddd",
                borderRadius: 12,
                padding: "1.5rem",
                position: "relative",
                background: isCurrent ? "#f0f0ff" : "#fff",
              }}
            >
              {isPopular && (
                <div style={{
                  position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)",
                  background: "#6c63ff", color: "#fff", padding: "2px 16px", borderRadius: 12, fontSize: 12
                }}>
                  Most Popular
                </div>
              )}

              <h2 style={{ marginTop: isPopular ? "0.5rem" : 0 }}>
                {tierKey === "free" ? "🆓" : tierKey === "plus" ? "⭐" : "🚀"} {tier.name}
              </h2>
              <p style={{ fontSize: "1.5rem", fontWeight: "bold", margin: "0.5rem 0" }}>
                {tier.price_label}
              </p>

              <ul style={{ listStyle: "none", padding: 0, margin: "1rem 0" }}>
                {FEATURES.map((f) => (
                  <li key={f.key} style={{ padding: "4px 0", borderBottom: "1px solid #f0f0f0" }}>
                    {f.label}: <strong>{f.format((tier as any)[f.key])}</strong>
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <div>
                  <button disabled style={{
                    width: "100%", padding: "10px", borderRadius: 8,
                    background: "#e0e0e0", border: "none", cursor: "default"
                  }}>
                    Current Plan ✓
                  </button>
                  {tierKey !== "free" && (
                    <button
                      onClick={handleCancel}
                      style={{
                        width: "100%", padding: "8px", borderRadius: 8, marginTop: "0.5rem",
                        background: "transparent", border: "1px solid #dc3545", color: "#dc3545", cursor: "pointer"
                      }}
                    >
                      Cancel Subscription
                    </button>
                  )}
                </div>
              ) : tierKey !== "free" ? (
                <button
                  onClick={() => handleSubscribe(tierKey)}
                  disabled={subscribing === tierKey}
                  style={{
                    width: "100%", padding: "10px", borderRadius: 8,
                    background: isPopular ? "#6c63ff" : "#333",
                    color: "#fff", border: "none", cursor: "pointer",
                    opacity: subscribing === tierKey ? 0.6 : 1,
                  }}
                >
                  {subscribing === tierKey ? "Redirecting..." : `Subscribe to ${tier.name}`}
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
