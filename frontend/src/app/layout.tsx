import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Polymarket News",
  description: "AI-generated news articles from prediction market data",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
