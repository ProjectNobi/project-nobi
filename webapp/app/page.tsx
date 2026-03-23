import Link from "next/link";
import Navbar from "@/components/Navbar";

const FEATURES = [
  {
    icon: "🧠",
    title: "Remembers You",
    description:
      "Nori remembers your name, preferences, and conversations. The more you chat, the more personal it gets.",
  },
  {
    icon: "🔒",
    title: "Privacy First",
    description:
      "Your memories are encrypted at rest (AES-128, server-side) and stored securely. Export or delete them anytime — you're always in control.",
  },
  {
    icon: "🌍",
    title: "20+ Languages",
    description:
      "Chat in English, Chinese, Spanish, Hindi, Japanese, and many more. Nori adapts to your language.",
  },
  {
    icon: "⛓️",
    title: "Decentralized",
    description:
      "Powered by Bittensor's decentralized network. No single company controls your companion.",
  },
  {
    icon: "💬",
    title: "Natural Conversations",
    description:
      "Talk like you would with a friend. Nori understands emotions, context, and nuance.",
  },
  {
    icon: "🎯",
    title: "Always Improving",
    description:
      "Miners compete to provide the best companion experience. Quality improves every day.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      <Navbar />

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-nori-50 via-white to-warm-50 dark:from-gray-900 dark:via-bg-dark dark:to-gray-900" />
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 pt-20 pb-24 sm:pt-28 sm:pb-32">
          <div className="text-center space-y-6">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-nori-100 dark:bg-nori-900/30 text-nori-700 dark:text-nori-300 text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse-soft" />
              Built on Bittensor
            </div>

            {/* Heading */}
            <h1 className="text-4xl sm:text-6xl font-bold text-gray-900 dark:text-white leading-tight">
              Meet{" "}
              <span className="bg-gradient-to-r from-nori-600 to-warm-500 bg-clip-text text-transparent">
                Nori
              </span>
              <br />
              Your AI Companion
            </h1>

            {/* Subtitle */}
            <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
              A warm, private AI friend that remembers you. Chat naturally,
              build memories together, and feel truly understood.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
              <Link href="/chat" className="btn-primary text-lg px-8 py-4">
                Try Nori 💬
              </Link>
              <Link href="/onboarding" className="btn-secondary text-lg px-8 py-4">
                Learn More
              </Link>
            </div>
          </div>

          {/* Chat Preview */}
          <div className="mt-16 max-w-lg mx-auto">
            <div className="card p-6 space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-nori-500 to-warm-500 flex items-center justify-center text-sm">
                  🤖
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-2xl rounded-tl-md px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                  Hey! I&apos;m Nori 👋 What should I call you?
                </div>
              </div>
              <div className="flex items-start gap-3 flex-row-reverse">
                <div className="w-8 h-8 rounded-full bg-nori-100 dark:bg-nori-900/50 flex items-center justify-center text-sm">
                  👤
                </div>
                <div className="bg-nori-600 text-white rounded-2xl rounded-tr-md px-4 py-3 text-sm">
                  Hi Nori! I&apos;m Alex 😊
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-nori-500 to-warm-500 flex items-center justify-center text-sm">
                  🤖
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-2xl rounded-tl-md px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                  Nice to meet you, Alex! 🎉 I&apos;ll remember that. So tell me — what&apos;s
                  been on your mind today?
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20 sm:py-28">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
              Why Nori?
            </h2>
            <p className="mt-4 text-lg text-gray-600 dark:text-gray-400">
              More than a chatbot — a companion that grows with you.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="card p-6 hover:scale-[1.02] transition-transform duration-200"
              >
                <div className="text-3xl mb-3">{feature.icon}</div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 bg-gradient-to-br from-nori-600 to-nori-800">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Ready to meet your companion?
          </h2>
          <p className="text-nori-100 text-lg mb-8">
            No signup needed. Just start chatting and Nori will remember you.
          </p>
          <Link
            href="/chat"
            className="inline-flex items-center justify-center px-8 py-4 rounded-xl bg-white text-nori-700 font-semibold text-lg hover:bg-nori-50 transition-colors shadow-xl"
          >
            Start Chatting →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-gray-200 dark:border-gray-800">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <span className="text-xl">🤖</span>
              <span className="font-medium">Project Nobi</span>
            </div>
            <div className="flex items-center gap-6 text-sm text-gray-500 dark:text-gray-400">
              <a
                href="https://github.com/ProjectNobi/project-nobi"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                GitHub
              </a>
              <a
                href="https://bittensor.com"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                Bittensor
              </a>
              <span>Subnet 272</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
