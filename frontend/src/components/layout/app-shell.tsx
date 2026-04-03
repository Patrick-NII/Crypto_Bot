"use client";

import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ChatWrapper } from "@/components/ai/chat-wrapper";

const PUBLIC_ROUTES = ["/", "/login", "/register", "/forgot-password", "/verify-email", "/reset-password", "/pricing"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // During SSR/prerender, just render children without layout
  if (!mounted) {
    return <>{children}</>;
  }

  const isPublic = PUBLIC_ROUTES.includes(pathname);

  if (isPublic) {
    return <>{children}</>;
  }

  return (
    <>
      <Sidebar />
      <div className="flex flex-col min-h-screen md:pl-60 transition-all duration-300">
        <Header />
        <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
          {children}
        </main>
      </div>
      <ChatWrapper />
    </>
  );
}
