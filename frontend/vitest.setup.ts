import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

import viMessages from "./messages/vi.json";
import enMessages from "./messages/en.json";

function message(namespace: string | undefined, key: string, values?: Record<string, unknown>) {
  // The legacy Chat unit suite asserts its established English accessible labels. Keep that suite
  // deterministic while the rest of the app exercises the default Vietnamese catalog.
  const catalog = namespace === "chat" ? enMessages : viMessages;
  const path = [...(namespace ? namespace.split(".") : []), ...key.split(".")];
  const template = path.reduce<unknown>((current, segment) => {
    if (!current || typeof current !== "object") return undefined;
    return (current as Record<string, unknown>)[segment];
  }, catalog);
  if (typeof template !== "string") return key;
  return Object.entries(values ?? {}).reduce(
    (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
    template,
  );
}

const translators = new Map<string, (key: string, values?: Record<string, unknown>) => string>();

function translator(namespace?: string) {
  const cacheKey = namespace ?? "";
  const cached = translators.get(cacheKey);
  if (cached) return cached;
  const created = (key: string, values?: Record<string, unknown>) =>
    message(namespace, key, values);
  translators.set(cacheKey, created);
  return created;
}

vi.mock("next-intl", () => ({
  NextIntlClientProvider: ({ children }: { children: unknown }) => children,
  useLocale: () => "vi",
  useTranslations: (namespace?: string) => translator(namespace),
}));

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
});
