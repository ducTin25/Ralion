"use client";

import { useCallback, useSyncExternalStore } from "react";

export type MemberTheme = "light" | "dark";

const STORAGE_KEY = "ralion-member-theme";
const THEME_EVENT = "ralion-member-theme-change";

function preferredTheme(): MemberTheme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function subscribe(onStoreChange: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(THEME_EVENT, onStoreChange);
  media.addEventListener("change", onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(THEME_EVENT, onStoreChange);
    media.removeEventListener("change", onStoreChange);
  };
}

export function usePersistentTheme() {
  const theme = useSyncExternalStore<MemberTheme>(subscribe, preferredTheme, () => "light");
  const toggleTheme = useCallback(() => {
    window.localStorage.setItem(STORAGE_KEY, theme === "light" ? "dark" : "light");
    window.dispatchEvent(new Event(THEME_EVENT));
  }, [theme]);
  return { theme, toggleTheme };
}
