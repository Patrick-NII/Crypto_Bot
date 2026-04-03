"use client";

import { cn } from "@/lib/utils";

interface LoadingProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeMap = {
  sm: "h-6 w-6",
  md: "h-10 w-10",
  lg: "h-16 w-16",
};

export function Loading({ size = "md", className, label }: LoadingProps) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-3", className)}
      role="status"
    >
      <div className={cn("relative", sizeMap[size])}>
        {/* Outer ring */}
        <div
          className={cn(
            "absolute inset-0 rounded-full border-2 border-[rgba(255,255,255,0.06)]",
            sizeMap[size]
          )}
        />
        {/* Spinning gradient ring */}
        <div
          className={cn(
            "absolute inset-0 animate-spin-slow rounded-full border-2 border-transparent border-t-[#06d6a0] border-r-[#c6f135]",
            sizeMap[size]
          )}
        />
        {/* Inner glow dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-1.5 w-1.5 rounded-full bg-[#06d6a0] animate-pulse-glow" />
        </div>
      </div>
      {label && (
        <p className="text-sm text-[#8888a0] font-medium">{label}</p>
      )}
      <span className="sr-only">{label ?? "Loading..."}</span>
    </div>
  );
}
