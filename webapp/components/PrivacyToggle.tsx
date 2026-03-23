"use client";

/**
 * Project Nobi — Privacy Mode Toggle
 * ====================================
 * UI component for enabling/disabling on-device memory extraction.
 * When enabled, memories are extracted in the browser and only encrypted
 * blobs are sent to the server. Raw conversation text never leaves the device.
 */

import { useEffect, useState } from "react";
import {
  loadPrivacySettings,
  savePrivacySettings,
  isPrivacyModeSupported,
  type PrivacySettings,
} from "../lib/memory-sync";

interface PrivacyToggleProps {
  /** Called whenever settings change */
  onChange?: (settings: PrivacySettings) => void;
  /** Show compact mode (just icon + status) */
  compact?: boolean;
}

export default function PrivacyToggle({ onChange, compact = false }: PrivacyToggleProps) {
  const [settings, setSettings] = useState<PrivacySettings>({ enabled: false });
  const [supported, setSupported] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => {
    setMounted(true);
    const loaded = loadPrivacySettings();
    setSettings(loaded);
    setSupported(isPrivacyModeSupported());
  }, []);

  const toggle = () => {
    if (!supported) return;
    const next: PrivacySettings = { ...settings, enabled: !settings.enabled };
    setSettings(next);
    savePrivacySettings(next);
    onChange?.(next);
  };

  if (!mounted) return <div className="w-8 h-8" />;

  // ─── Compact mode: just icon + tooltip ────────────────────────────────────
  if (compact) {
    return (
      <div className="relative inline-flex items-center">
        <button
          onClick={toggle}
          onMouseEnter={() => { if (window.matchMedia('(hover: hover)').matches) setShowTooltip(true); }}
          onMouseLeave={() => setShowTooltip(false)}
          disabled={!supported}
          className={`
            flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition-all text-xs font-medium
            ${settings.enabled
              ? "bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 ring-1 ring-green-300 dark:ring-green-700"
              : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"}
            ${!supported ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          `}
          aria-label={settings.enabled ? "Privacy mode on — click to disable" : "Privacy mode off — click to enable"}
        >
          {settings.enabled ? "🔒" : "🛡️"}
          <span className="hidden sm:inline">
            {settings.enabled ? "Private" : "Standard"}
          </span>
        </button>

        {showTooltip && (
          <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg whitespace-nowrap z-50 pointer-events-none max-w-xs text-center shadow-lg">
            {!supported
              ? "Privacy mode not supported in this browser"
              : settings.enabled
              ? "🔒 On-device privacy ON — memories extracted locally, only encrypted data sent"
              : "🔓 Click to enable on-device privacy — your data stays in your browser"}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-900" />
          </div>
        )}
      </div>
    );
  }

  // ─── Full mode: detailed card ─────────────────────────────────────────────
  return (
    <div className={`
      rounded-xl border p-4 transition-all
      ${settings.enabled
        ? "border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-950"
        : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50"}
    `}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{settings.enabled ? "🔒" : "🔓"}</span>
            <span className="font-semibold text-sm text-gray-900 dark:text-gray-100">
              On-Device Privacy
            </span>
            {!supported && (
              <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300 px-2 py-0.5 rounded-full">
                Not supported
              </span>
            )}
          </div>

          <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
            {settings.enabled ? (
              <>
                <span className="font-medium text-green-700 dark:text-green-400">Active</span>
                {" — "}Your memories are extracted locally in your browser. Only encrypted data is sent to the server. Nobi cannot read your thoughts.
              </>
            ) : (
              <>
                <span className="font-medium">Disabled</span>
                {" — "}Memory extraction happens on the server. Enable for maximum privacy.
              </>
            )}
          </p>

          {!supported && (
            <p className="text-xs text-yellow-700 dark:text-yellow-400 mt-1">
              Your browser doesn't support the Web Crypto API needed for on-device encryption.
            </p>
          )}
        </div>

        {/* Toggle switch */}
        <button
          onClick={toggle}
          disabled={!supported}
          role="switch"
          aria-checked={settings.enabled}
          aria-label="Toggle on-device privacy"
          className={`
            relative flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200
            focus:outline-none focus:ring-2 focus:ring-offset-2
            ${settings.enabled
              ? "bg-green-500 focus:ring-green-500"
              : "bg-gray-300 dark:bg-gray-600 focus:ring-gray-400"}
            ${!supported ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          `}
        >
          <span
            className={`
              absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200
              ${settings.enabled ? "translate-x-5" : "translate-x-0"}
            `}
          />
        </button>
      </div>

      {settings.enabled && (
        <div className="mt-3 pt-3 border-t border-green-200 dark:border-green-800">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs text-green-700 dark:text-green-400 font-medium">
              End-to-end encrypted · AES-256-GCM · Keys never leave your device
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
