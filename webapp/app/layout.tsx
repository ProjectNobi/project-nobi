import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/styles/globals.css";
import ConsentBanner from "@/components/ConsentBanner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Nori — Your Personal AI Companion",
  description:
    "A warm, private AI companion that remembers you. Built on Bittensor by Project Nobi.",
  icons: {
    icon: "/nori-avatar.svg",
  },
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    viewportFit: "cover",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const t = localStorage.getItem('nobi_theme');
                if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                  document.documentElement.classList.add('dark');
                }
              } catch(e) {}
            `,
          }}
        />
      </head>
      <body className={inter.className}>
        {children}
        <ConsentBanner />
        <footer className="w-full py-3 text-center text-xs text-gray-400 dark:text-gray-600 border-t border-gray-100 dark:border-gray-800 mt-auto">
          <a href="https://projectnobi.ai/privacy.html" className="hover:underline mx-2">Privacy Policy</a>
          ·
          <a href="https://projectnobi.ai/terms.html" className="hover:underline mx-2">Terms of Service</a>
          ·
          <span className="mx-2">© 2026 Project Nobi</span>
        </footer>
      </body>
    </html>
  );
}
