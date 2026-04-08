"use client";

import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { AuthGuard } from "@/components/auth/auth-guard";
import { OnboardingModal } from "@/components/auth/onboarding-modal";
import { Sidebar } from "@/components/layout/sidebar";
import { ChatWrapper } from "@/components/ai/chat-wrapper";

const PUBLIC_ROUTES = ["/", "/login", "/register", "/forgot-password", "/verify-email", "/reset-password", "/pricing", "/terms"];

const SIDEBAR_KEY = "gluetrade-sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Start with server-safe defaults to avoid hydration mismatch
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Sync from client state after mount
    const syncSidebar = () => setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === "true");
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    const frame = window.requestAnimationFrame(() => {
      syncSidebar();
      checkMobile();
    });

    window.addEventListener("resize", checkMobile);

    const interval = setInterval(syncSidebar, 300);

    return () => {
      window.cancelAnimationFrame(frame);
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
        <main className="flex-1 px-3 pb-7 pt-14 md:px-5 md:pb-6 md:pt-5 xl:px-6">
          <div className="mx-auto w-full max-w-[1920px] border-x border-[var(--glass-border)]/50 px-4 md:px-7 xl:px-10 2xl:max-w-[2320px] 2xl:px-12">
            <AuthGuard>{children}</AuthGuard>
          </div>
        </main>
      </div>
      <ChatWrapper />
      <OnboardingModal />
    </>
  );
}
