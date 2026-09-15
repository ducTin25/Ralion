import type { Locale } from "./routing";

const loaders = {
  vi: () => import("../../messages/vi.json").then((module) => module.default),
  en: () => import("../../messages/en.json").then((module) => module.default),
} satisfies Record<Locale, () => Promise<Record<string, unknown>>>;

export function loadMessages(locale: Locale) {
  return loaders[locale]();
}
