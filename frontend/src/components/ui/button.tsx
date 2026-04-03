import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "success" | "accent";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-gradient-to-br from-[var(--page-accent)] to-[var(--page-accent)] text-[#0a0a10] font-semibold hover:shadow-lg hover:scale-[1.02]",
  accent: "accent-bg accent-text font-semibold hover:scale-[1.02]",
  secondary: "liquid-glass-pill border border-[var(--glass-border)] text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
  danger: "bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/20 hover:bg-[#ef4444]/25",
  ghost: "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--glass-bg)]",
  success: "bg-[#22c55e] text-white font-semibold hover:bg-[#16a34a] hover:scale-[1.02]",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-xl",
  md: "px-4 py-2.5 text-sm rounded-2xl",
  lg: "px-6 py-3 text-base rounded-2xl",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading,
  disabled,
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-all duration-200",
        "focus:outline-none focus:ring-2 focus:ring-[var(--page-accent)]/40",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
