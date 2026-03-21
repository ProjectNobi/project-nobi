"use client";

import { useEffect, useState } from "react";

const CONSENT_KEY = "nobi_consent_accepted";

export default function ConsentBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const accepted = localStorage.getItem(CONSENT_KEY);
      if (!accepted) {
        setVisible(true);
      }
    } catch {
      // localStorage not available (SSR guard)
    }
  }, []);

  const handleAccept = () => {
    try {
      localStorage.setItem(CONSENT_KEY, "true");
    } catch {
      // ignore
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 p-4 bg-gray-900 border-t border-gray-700 shadow-2xl"
      role="dialog"
      aria-label="Consent banner"
    >
      <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-6">
        <p className="text-sm text-gray-300 flex-1">
          By using Nori, you agree to our{" "}
          <a
            href="https://projectnobi.ai/terms.html"
            className="text-purple-400 underline hover:text-purple-300"
            target="_blank"
            rel="noopener noreferrer"
          >
            Terms of Service
          </a>{" "}
          and{" "}
          <a
            href="https://projectnobi.ai/privacy.html"
            className="text-purple-400 underline hover:text-purple-300"
            target="_blank"
            rel="noopener noreferrer"
          >
            Privacy Policy
          </a>
          . You must be at least <strong className="text-white">18 years old</strong>{" "}
           to use this service.
        </p>
        <button
          onClick={handleAccept}
          className="flex-shrink-0 px-5 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-semibold rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-900"
          aria-label="Accept terms and privacy policy"
        >
          I Agree
        </button>
      </div>
    </div>
  );
}
