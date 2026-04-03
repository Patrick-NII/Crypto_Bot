import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { ChatWrapper } from "@/components/ai/chat-wrapper";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <AuthGuard>
      <Sidebar />

      <div className="flex flex-col min-h-screen md:pl-60 transition-all duration-300">
        <Header />

        <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
          {children}
        </main>
      </div>

      <ChatWrapper />
    </AuthGuard>
  );
}
