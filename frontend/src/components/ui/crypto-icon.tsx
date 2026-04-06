"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * Crypto icon using Binance CDN (most reliable, no mapping needed).
 * Falls back to provided imageUrl, then letter badge.
 *
 * Binance CDN pattern: https://bin.bnbstatic.com/image/admin_mgs_image_upload/20201110/87496d50-2408-43e1-ad4c-78b47b448a6a.png
 * Simpler: https://assets.coingecko.com/coins/images/.../small/....png (needs ID)
 *
 * Best approach: use the Binance static icon CDN which works with ticker symbols directly.
 */

type IconSize = "xs" | "sm" | "md" | "lg" | "xl";

const SIZE_MAP: Record<IconSize, { box: string; text: string; px: number }> = {
  xs: { box: "h-4 w-4", text: "text-[8px]", px: 16 },
  sm: { box: "h-5 w-5", text: "text-[9px]", px: 20 },
  md: { box: "h-7 w-7", text: "text-[11px]", px: 28 },
  lg: { box: "h-10 w-10", text: "text-[14px]", px: 40 },
  xl: { box: "h-12 w-12", text: "text-[16px]", px: 48 },
};

// Binance CDN: works for most listed tokens, just lowercase the symbol
function binanceIconUrl(symbol: string): string {
  const s = symbol.toUpperCase();
  return `https://cdn.jsdelivr.net/gh/nicehash/coinicons@main/crypto/${s.toLowerCase()}.svg`;
}

// Backup CDN: CryptoIcons (community maintained, very broad coverage)
function cryptoIconUrl(symbol: string): string {
  return `https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/32/color/${symbol.toLowerCase()}.png`;
}

// Deterministic pastel color from symbol
function symbolColor(symbol: string): string {
  let hash = 0;
  for (let i = 0; i < symbol.length; i++) hash = symbol.charCodeAt(i) + ((hash << 5) - hash);
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 50%, 45%)`;
}

interface CryptoIconProps {
  symbol: string;
  imageUrl?: string;
  size?: IconSize;
  className?: string;
}

export function CryptoIcon({ symbol, imageUrl, size = "sm", className }: CryptoIconProps) {
  const s = SIZE_MAP[size];
  const upper = symbol.toUpperCase();
  const letter = upper.slice(0, upper.length >= 4 ? 2 : 1);
  const bg = useMemo(() => symbolColor(upper), [upper]);
  const [imgFailed, setImgFailed] = useState(0); // 0 = try primary, 1 = try backup, 2 = letter only

  // Priority: provided imageUrl → NiceHash CDN (SVG) → CryptoIcons (PNG) → letter
  const srcs = useMemo(() => {
    const urls: string[] = [];
    if (imageUrl) urls.push(imageUrl);
    urls.push(binanceIconUrl(upper));
    urls.push(cryptoIconUrl(upper));
    return urls;
  }, [imageUrl, upper]);

  const currentSrc = imgFailed < srcs.length ? srcs[imgFailed] : null;

  return (
    <span
      className={cn("relative inline-flex shrink-0 items-center justify-center rounded-full overflow-hidden", s.box, className)}
      style={{ background: currentSrc ? "transparent" : bg }}
    >
      {currentSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={currentSrc}
          alt={upper}
          width={s.px}
          height={s.px}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setImgFailed((prev) => prev + 1)}
        />
      ) : (
        <span className={cn("flex items-center justify-center font-bold text-white/90", s.text)}>
          {letter}
        </span>
      )}
    </span>
  );
}
