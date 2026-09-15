import { describe, expect, it } from "vitest";

import type { CurrentUser } from "@/features/auth/session";

import { defaultLandingPath, projectPortalPath, resolvePostLoginPath } from "./routing";

function user(
  systemRole: CurrentUser["system_role"],
  memberships: CurrentUser["memberships"] = [],
): CurrentUser {
  return {
    user_id: 1,
    display_name: "Test User",
    email: "test@onboarding.dev",
    system_role: systemRole,
    status: "ACTIVE",
    response_length: "STANDARD",
    response_tone: "NEUTRAL",
    memberships,
    expires_at: null,
  };
}

const engineerMembership: CurrentUser["memberships"][number] = {
  membership_id: 11,
  project_id: 7,
  project_name: "Payments",
  project_key: "PAY",
  project_role: "ENGINEER",
  status: "ACTIVE",
  project_status: "ACTIVE",
};

describe("post-login routing", () => {
  it.each([
    ["ADMIN", "/admin"],
    ["HR", "/hr"],
    [null, "/select-project"],
  ] as const)("uses the correct landing page for %s", (role, expected) => {
    expect(defaultLandingPath(user(role))).toBe(expected);
  });

  it("keeps an authorized admin destination", () => {
    expect(resolvePostLoginPath(user("ADMIN"), "/admin/users?page=2")).toBe("/admin/users?page=2");
  });

  it("strips a locale prefix before authorizing the return destination", () => {
    expect(resolvePostLoginPath(user("ADMIN"), "/en/admin/users?page=2")).toBe(
      "/admin/users?page=2",
    );
  });

  it("does not send HR users back to an admin route", () => {
    expect(resolvePostLoginPath(user("HR"), "/admin/projects")).toBe("/hr");
  });

  it("always shows the selector for project-scoped users, even with exactly one membership", () => {
    expect(defaultLandingPath(user(null, [engineerMembership]))).toBe("/select-project");
    expect(resolvePostLoginPath(user(null, [engineerMembership]), "/select-project")).toBe(
      "/select-project",
    );
  });

  it("keeps the selector for multiple active memberships and ignores inactive ones", () => {
    const inactive = {
      ...engineerMembership,
      membership_id: 12,
      project_id: 8,
      status: "INACTIVE" as const,
    };
    const secondActive = {
      ...engineerMembership,
      membership_id: 13,
      project_id: 9,
      project_role: "PM" as const,
    };
    expect(defaultLandingPath(user(null, [engineerMembership, inactive]))).toBe("/select-project");
    expect(defaultLandingPath(user(null, [engineerMembership, secondActive]))).toBe(
      "/select-project",
    );
  });

  it("builds canonical portal URLs from validated project context", () => {
    expect(projectPortalPath("ENGINEER", 7)).toBe("/user?project=7");
    expect(projectPortalPath("PM", 9)).toBe("/product-manager?project=9");
  });

  it.each(["/admin", "/hr", "/user?project=1", "/product-manager?project=1"])(
    "forces project-scoped users through project selection instead of %s",
    (requested) => {
      expect(resolvePostLoginPath(user(null), requested)).toBe("/select-project");
    },
  );

  it("rejects external and protocol-relative destinations", () => {
    expect(resolvePostLoginPath(user("ADMIN"), "https://example.com/admin")).toBe("/admin");
    expect(resolvePostLoginPath(user("ADMIN"), "//example.com/admin")).toBe("/admin");
  });
});
