import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Telex — Autonomous Revenue Recovery & Self-Healing Agent for Razorpay",
  description:
    "Built for the Razorpay Pay 2026 Buildathon. Autonomous AI revenue recovery & self-healing patch agent for live Razorpay payment failures, webhook mismatches, and SDK breaks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#000000" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-black text-[#E4E4E7] antialiased selection:bg-white selection:text-black overflow-x-hidden min-h-screen">
        {children}
      </body>
    </html>
  );
}
