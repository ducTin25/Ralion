import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  SHALLOW_NAVIGATION_EVENT,
  canShallowNavigate,
  shallowNavigate,
} from "@/lib/shallowNavigation";

describe("shallow navigation", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/vi/user?project=1");
  });

  it("updates only the query on the current localized route", () => {
    const changed = vi.fn();
    window.addEventListener(SHALLOW_NAVIGATION_EVENT, changed, { once: true });

    expect(shallowNavigate("/user?project=1&view=policy")).toBe(true);
    expect(window.location.pathname).toBe("/vi/user");
    expect(window.location.search).toBe("?project=1&view=policy");
    expect(changed).toHaveBeenCalledOnce();
  });

  it("keeps cross-route navigation on the App Router", () => {
    expect(canShallowNavigate("/select-project")).toBe(false);
    expect(shallowNavigate("/select-project")).toBe(false);
    expect(window.location.pathname).toBe("/vi/user");
  });

  it("supports replace semantics without adding a history entry", () => {
    const before = window.history.length;
    expect(shallowNavigate("/user?project=2", true)).toBe(true);
    expect(window.location.search).toBe("?project=2");
    expect(window.history.length).toBe(before);
  });
});
