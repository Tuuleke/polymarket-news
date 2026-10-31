import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Self-hosted at build time: visitors' browsers never contact Google Fonts.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "Polymarket News",
  description: "AI-generated articles for prediction market moves",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        {/* Sets dark class + no-transition before React hydrates — prevents FOUC */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var s=localStorage.getItem('pmn-theme');var d=s?s==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d);document.documentElement.classList.add('no-transition');}catch(e){}})();`,
          }}
        />
      </head>
      <body>
        {children}
        {/* Remove no-transition after first paint so subsequent theme switches animate */}
        <script
          dangerouslySetInnerHTML={{
            __html: `requestAnimationFrame(function(){requestAnimationFrame(function(){document.documentElement.classList.remove('no-transition');});});`,
          }}
        />
      </body>
    </html>
  );
}
