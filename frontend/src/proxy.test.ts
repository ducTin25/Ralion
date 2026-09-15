import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "./proxy";

describe("locale and session proxy", () => {
  it("redirects unprefixed routes to Vietnamese", () => {
    const response = proxy(new NextRequest("https://ralion.test/login?from=home"));
    expect(response.headers.get("location")).toBe("https://ralion.test/vi/login?from=home");
  });

  it("keeps locale in protected login redirects", () => {
    const response = proxy(new NextRequest("https://ralion.test/en/admin/users?page=2"));
    const location = new URL(response.headers.get("location")!);
    expect(location.pathname).toBe("/en/login");
    expect(location.searchParams.get("next")).toBe("/en/admin/users?page=2");
  });

  it("passes locale to authenticated application requests", () => {
    const request = new NextRequest("https://ralion.test/en/admin", {
      headers: { cookie: "ralion_session=test" },
    });
    const response = proxy(request);
    expect(response.headers.get("x-middleware-request-x-ralion-locale")).toBe("en");
  });
});
