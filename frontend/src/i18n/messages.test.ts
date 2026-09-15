import { describe, expect, it } from "vitest";

import en from "../../messages/en.json";
import vi from "../../messages/vi.json";

function leafKeys(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [prefix];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    leafKeys(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("translation catalogs", () => {
  it("have exactly the same message keys", () => {
    expect(leafKeys(en).sort()).toEqual(leafKeys(vi).sort());
  });

  it("do not contain empty translations", () => {
    for (const catalog of [vi, en]) {
      const empty = leafKeys(catalog).filter((key) => {
        const value = key.split(".").reduce<unknown>((current, part) => {
          if (!current || typeof current !== "object") return undefined;
          return (current as Record<string, unknown>)[part];
        }, catalog);
        return typeof value !== "string" || value.trim().length === 0;
      });
      expect(empty).toEqual([]);
    }
  });

  it("include every PM task status used by the member progress drawer", () => {
    const requiredStatusKeys = [
      "statusNotStarted",
      "statusInProgress",
      "statusDone",
      "statusBlocked",
    ];

    for (const catalog of [vi, en]) {
      const pmUi = catalog.pmUi as Record<string, string>;
      for (const key of requiredStatusKeys) {
        expect(pmUi[key]).toEqual(expect.any(String));
        expect(pmUi[key].trim()).not.toBe("");
      }
    }
  });
});
