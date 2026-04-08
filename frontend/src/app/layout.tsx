import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { AppShell } from "@/components/layout/app-shell";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { CurrencyProvider } from "@/components/providers/currency-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { PortfolioProvider } from "@/components/providers/portfolio-provider";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "GlueTrade | AI-Powered Crypto Trading",
  description: "Autonomous crypto trading with AI agents, real-time analytics, and professional tools.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-background text-foreground antialiased">
        <ThemeProvider>
          <CurrencyProvider>
            <AuthProvider>
              <PortfolioProvider>
                <AppShell>{children}</AppShell>
              </PortfolioProvider>
            </AuthProvider>
          </CurrencyProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
