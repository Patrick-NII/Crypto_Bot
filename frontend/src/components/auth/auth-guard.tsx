"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
    } else {
      setChecking(false);
    }
  }, [router]);

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0d0d12]">
        <Loader2 className="h-8 w-8 animate-spin text-[#06d6a0]" />
      </div>
    );
  }

  return <>{children}</>;
}
