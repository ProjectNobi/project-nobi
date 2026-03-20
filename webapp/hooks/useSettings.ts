"use client";

import { useState, useCallback, useEffect } from "react";
import { STORAGE_KEYS, DEFAULT_SETTINGS } from "@/lib/constants";
import type { UserSettings } from "@/lib/types";

export function useSettings() {
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem(STORAGE_KEYS.SETTINGS);
    if (saved) {
      try {
        setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(saved) });
      } catch {
        // ignore parse errors
      }
    }
  }, []);

  const updateSettings = useCallback(
    (updates: Partial<UserSettings>) => {
      setSettings((prev) => {
        const next = { ...prev, ...updates };
        if (typeof window !== "undefined") {
          localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(next));
        }
        return next;
      });
    },
    []
  );

  const isOnboarded = useCallback((): boolean => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEYS.ONBOARDED) === "true";
  }, []);

  const setOnboarded = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEYS.ONBOARDED, "true");
    }
  }, []);

  return {
    settings,
    updateSettings,
    isOnboarded,
    setOnboarded,
  };
}
