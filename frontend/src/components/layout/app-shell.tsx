"use client";

import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { AuthGuard } from "@/components/auth/auth-guard";
import { OnboardingModal } from "@/components/auth/onboarding-modal";
import { Sidebar } from "@/components/layout/sidebar";
import { ChatWrapper } from "@/components/ai/chat-wrapper";

const PUBLIC_ROUTES = ["/", "/login", "/register", "/forgot-password", "/verify-email", "/reset-password", "/pricing", "/terms"];

const SIDEBAR_KEY = "okamoey-sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Start with server-safe defaults to avoid hydration mismatch
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Sync from client state after mount
    setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === "true");
    setIsMobile(window.innerWidth < 768);

    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", checkMobile);

    const interval = setInterval(() => {
      setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === "true");
    }, 300);

    return () => {
      window.removeEventListener("resize", checkMobile);
      clearInterval(interval);
    };
  }, []);

  const isPublic = PUBLIC_ROUTES.includes(pathname);
  if (isPublic) return <>{children}</>;

  const offset = isMobile ? 0 : sidebarCollapsed ? 68 : 240;

  return (
    <>
      <Sidebar />
      <div
        className="flex flex-col min-h-screen transition-all duration-300 relative z-[1]"
        style={{ paddingLeft: `${offset}px` }}
      >
        <main className="flex-1 p-3 md:p-5 pt-14 md:pt-5 pb-6 md:pb-5">
          <AuthGuard>{children}</AuthGuard>
        </main>
      </div>
      <ChatWrapper />
      <OnboardingModal />
    </>
  );
}
