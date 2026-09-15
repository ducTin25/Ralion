import { describe, expect, it } from "vitest";

import { isLocale, localeFromPathname, localizePath, stripLocale } from "./routing";

describe("locale routing helpers", () => {
  it("accepts only supported locales", () => {
    expect(isLocale("vi")).toBe(true);
    expect(isLocale("en")).toBe(true);
    expect(isLocale("fr")).toBe(false);
  });

  it("extracts and strips locale prefixes", () => {
    expect(localeFromPathname("/en/admin/users")).toBe("en");
    expect(localeFromPathname("/admin/users")).toBeNull();
    expect(stripLocale("/vi")).toBe("/");
    expect(stripLocale("/vi/admin/users")).toBe("/admin/users");
  });

  it("localizes paths without duplicating an existing prefix", () => {
    expect(localizePath("/", "vi")).toBe("/vi");
    expect(localizePath("/admin/users", "en")).toBe("/en/admin/users");
    expect(localizePath("/vi/admin/users", "en")).toBe("/en/admin/users");
  });
});
