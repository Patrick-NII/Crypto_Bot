"use client";

import { useEffect, useState } from "react";

const SIDEBAR_KEY = "gluetrade-sidebar-collapsed";
const MOBILE_BREAKPOINT = 768;

function readSidebarOffset() {
  if (typeof window === "undefined") return 0;
  if (window.innerWidth < MOBILE_BREAKPOINT) return 0;
  return localStorage.getItem(SIDEBAR_KEY) === "true" ? 68 : 240;
}

function lockDocumentScroll() {
  const body = document.body;
  const root = document.documentElement;
  const activeLocks = Number(body.dataset.modalLockCount ?? "0");

  if (activeLocks === 0) {
    body.dataset.modalOverflow = body.style.overflow;
    body.dataset.modalPaddingRight = body.style.paddingRight;
    root.dataset.modalOverflow = root.style.overflow;

    const scrollbarWidth = Math.max(0, window.innerWidth - root.clientWidth);
    body.style.overflow = "hidden";
    root.style.overflow = "hidden";
    if (scrollbarWidth > 0) {
      body.style.paddingRight = `${scrollbarWidth}px`;
    }
  }

  body.dataset.modalLockCount = String(activeLocks + 1);
}

function unlockDocumentScroll() {
  const body = document.body;
  const root = document.documentElement;
  const activeLocks = Number(body.dataset.modalLockCount ?? "0");
  const nextLocks = Math.max(0, activeLocks - 1);

  if (nextLocks === 0) {
    body.style.overflow = body.dataset.modalOverflow ?? "";
    body.style.paddingRight = body.dataset.modalPaddingRight ?? "";
    root.style.overflow = root.dataset.modalOverflow ?? "";

    delete body.dataset.modalLockCount;
    delete body.dataset.modalOverflow;
    delete body.dataset.modalPaddingRight;
    delete root.dataset.modalOverflow;
    return;
  }

  body.dataset.modalLockCount = String(nextLocks);
}

export function useModalViewport(active: boolean) {
  const [contentOffsetLeft, setContentOffsetLeft] = useState(0);

  useEffect(() => {
    if (!active) return;

    const syncOffset = () => setContentOffsetLeft(readSidebarOffset());
    syncOffset();

    window.addEventListener("resize", syncOffset);
    const interval = window.setInterval(syncOffset, 250);

    return () => {
      window.removeEventListener("resize", syncOffset);
      window.clearInterval(interval);
    };
  }, [active]);

  useEffect(() => {
    if (!active) return;

    lockDocumentScroll();
    return () => {
      unlockDocumentScroll();
    };
  }, [active]);

  return { contentOffsetLeft };
}
