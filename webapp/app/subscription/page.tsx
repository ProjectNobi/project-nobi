"use client";

export default function SubscriptionPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold text-center mb-2">🎉 Nori is Free for All Users!</h1>
      <p className="text-center text-gray-400 mb-10 text-lg">
        No subscriptions. No premium tiers. No limits. Every feature is available to everyone.
      </p>

      {/* Community Model */}
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">💚 How It Works</h2>
        <p className="text-gray-300 mb-4">
          Project Nobi is <strong>community-funded</strong> through the Bittensor network. Instead of charging users,
          the service is sustained by:
        </p>
        <ul className="space-y-3 text-gray-300">
          <li className="flex gap-3">
            <span className="text-xl">⛓️</span>
            <div>
              <strong className="text-white">Bittensor Emissions</strong> — The Nobi subnet earns TAO emissions
              from the network, which pay miners and validators for their work.
            </div>
          </li>
          <li className="flex gap-3">
            <span className="text-xl">🤝</span>
            <div>
              <strong className="text-white">Voluntary Community Staking</strong> — TAO holders who believe in the
              mission can stake on the Nobi subnet to increase its weight and funding.
            </div>
          </li>
          <li className="flex gap-3">
            <span className="text-xl">🔥</span>
            <div>
              <strong className="text-white">Zero Owner Profit</strong> — All subnet owner emissions are burned.
              No one profits from running this subnet.
            </div>
          </li>
        </ul>
      </div>

      {/* How to Support */}
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6 mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">🙌 Want to Support Nobi?</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <a
            href="https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-600 p-4 hover:border-nori-400/50 transition-colors block"
          >
            <h3 className="font-medium text-white mb-1">⛏️ Mine</h3>
            <p className="text-sm text-gray-400">Run a companion miner, earn TAO. No GPU needed.</p>
          </a>
          <a
            href="https://github.com/ProjectNobi/project-nobi/blob/main/docs/VALIDATING_GUIDE.md"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-600 p-4 hover:border-nori-400/50 transition-colors block"
          >
            <h3 className="font-medium text-white mb-1">✅ Validate</h3>
            <p className="text-sm text-gray-400">Stake TAO, earn dividends, ensure quality.</p>
          </a>
          <a
            href="https://github.com/ProjectNobi/project-nobi/blob/main/docs/VISION.md"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-600 p-4 hover:border-nori-400/50 transition-colors block"
          >
            <h3 className="font-medium text-white mb-1">💰 Stake</h3>
            <p className="text-sm text-gray-400">Stake TAO on the subnet to support free AI companionship.</p>
          </a>
          <a
            href="https://github.com/ProjectNobi/project-nobi/issues"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-600 p-4 hover:border-nori-400/50 transition-colors block"
          >
            <h3 className="font-medium text-white mb-1">💻 Contribute Code</h3>
            <p className="text-sm text-gray-400">Open source — pick an issue and build.</p>
          </a>
        </div>
      </div>

      {/* Links */}
      <div className="text-center space-y-3">
        <div className="flex flex-wrap justify-center gap-3">
          <a
            href="https://github.com/ProjectNobi/project-nobi/blob/main/docs/VISION.md"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-lg bg-nori-500 hover:bg-nori-600 text-white text-sm font-medium transition-colors"
          >
            Read Our Vision 📖
          </a>
          <a
            href="https://discord.gg/e6StezHM"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium transition-colors"
          >
            Join Discord 💬
          </a>
        </div>
        <p className="text-gray-500 text-xs mt-4">
          Staking TAO involves risk. This is not financial advice. See our{" "}
          <a href="https://github.com/ProjectNobi/project-nobi/blob/main/docs/VISION.md" className="text-nori-400 hover:underline">
            Vision
          </a>{" "}
          for details on the community model.
        </p>
      </div>
    </div>
  );
}
