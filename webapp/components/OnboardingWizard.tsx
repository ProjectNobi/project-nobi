"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSettings } from "@/hooks/useSettings";

const AGE_CONSENT_KEY = "nobi_age_confirmed";

const LANGUAGES = [
  { code: "en", name: "English", native: "English" },
  { code: "zh", name: "Chinese", native: "中文" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "es", name: "Spanish", native: "Español" },
  { code: "fr", name: "French", native: "Français" },
  { code: "ar", name: "Arabic", native: "العربية" },
  { code: "pt", name: "Portuguese", native: "Português" },
  { code: "ru", name: "Russian", native: "Русский" },
  { code: "ja", name: "Japanese", native: "日本語" },
  { code: "de", name: "German", native: "Deutsch" },
  { code: "ko", name: "Korean", native: "한국어" },
  { code: "vi", name: "Vietnamese", native: "Tiếng Việt" },
];

export default function OnboardingWizard() {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("en");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const { updateSettings, setOnboarded } = useSettings();
  const router = useRouter();

  const handleFinish = () => {
    updateSettings({ display_name: name, language });
    // Save age confirmation to localStorage
    try {
      localStorage.setItem(AGE_CONSENT_KEY, "true");
    } catch {
      // ignore
    }
    setOnboarded();
    router.push("/chat");
  };

  const steps = [
    // Step 0: Welcome
    <div key="welcome" className="text-center space-y-6 animate-fade-in">
      <div className="text-7xl mb-4">🤖</div>
      <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
        Meet Nori
      </h1>
      <p className="text-lg text-gray-600 dark:text-gray-400 max-w-md mx-auto">
        Your personal AI companion that remembers you, understands you, and
        grows with you.
      </p>
      {/* Age confirmation */}
      <label className="flex items-start gap-3 max-w-sm mx-auto text-left cursor-pointer">
        <input
          type="checkbox"
          checked={ageConfirmed}
          onChange={(e) => setAgeConfirmed(e.target.checked)}
          className="mt-1 w-4 h-4 accent-purple-600 flex-shrink-0"
        />
        <span className="text-sm text-gray-600 dark:text-gray-400">
          I confirm I am <strong>18 or older</strong>. (If you are under 13 years old,
          you may not use this service.) I agree to the{" "}
          <a href="/terms" className="text-purple-600 dark:text-purple-400 underline" target="_blank" rel="noopener noreferrer">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="/privacy" className="text-purple-600 dark:text-purple-400 underline" target="_blank" rel="noopener noreferrer">
            Privacy Policy
          </a>
          .
        </span>
      </label>
      <button
        onClick={() => ageConfirmed && setStep(1)}
        disabled={!ageConfirmed}
        className={`btn-primary text-lg px-8 py-4 ${!ageConfirmed ? "opacity-50 cursor-not-allowed" : ""}`}
        title={!ageConfirmed ? "Please confirm your age to continue" : undefined}
      >
        Get Started ✨
      </button>
    </div>,

    // Step 1: Name
    <div key="name" className="text-center space-y-6 animate-fade-in">
      <div className="text-5xl mb-2">👋</div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
        What should I call you?
      </h2>
      <p className="text-gray-600 dark:text-gray-400">
        This helps me make our conversations more personal.
      </p>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Your name (optional)"
        className="input-field max-w-xs mx-auto text-center"
        autoFocus
      />
      <div className="flex gap-3 justify-center">
        <button onClick={() => setStep(0)} className="btn-secondary">
          Back
        </button>
        <button onClick={() => setStep(2)} className="btn-primary">
          {name ? "Continue" : "Skip"}
        </button>
      </div>
    </div>,

    // Step 2: Language
    <div key="language" className="text-center space-y-6 animate-fade-in">
      <div className="text-5xl mb-2">🌍</div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
        Choose your language
      </h2>
      <p className="text-gray-600 dark:text-gray-400">
        I can chat in many languages!
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-md mx-auto">
        {LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            onClick={() => setLanguage(lang.code)}
            className={`px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
              language === lang.code
                ? "bg-nori-600 text-white shadow-lg"
                : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            {lang.native}
          </button>
        ))}
      </div>
      <div className="flex gap-3 justify-center">
        <button onClick={() => setStep(1)} className="btn-secondary">
          Back
        </button>
        <button onClick={handleFinish} className="btn-primary">
          Start Chatting 💬
        </button>
      </div>
    </div>,
  ];

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                i === step
                  ? "w-6 bg-nori-600"
                  : i < step
                  ? "bg-nori-400"
                  : "bg-gray-300 dark:bg-gray-600"
              }`}
            />
          ))}
        </div>
        {steps[step]}
      </div>
    </div>
  );
}
