"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "./ThemeToggle";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: "🏠" },
  { href: "/chat", label: "Chat", icon: "💬" },
  { href: "/memories", label: "Memories", icon: "🧠" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
  { href: "/support", label: "Support", icon: "🆘" },
  { href: "/help", label: "Help", icon: "❓" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200 dark:border-gray-800">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white"
          >
            <span className="text-2xl">🤖</span>
            <span className="bg-gradient-to-r from-nori-600 to-warm-500 bg-clip-text text-transparent">
              Nori
            </span>
          </Link>

          {/* Nav Links */}
          <div className="hidden sm:flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-nori-50 dark:bg-nori-900/30 text-nori-700 dark:text-nori-300"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  <span className="mr-1.5">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Mobile nav */}
      <div className="sm:hidden flex items-center justify-around border-t border-gray-200 dark:border-gray-800 py-2 px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                isActive
                  ? "text-nori-600 dark:text-nori-400"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
