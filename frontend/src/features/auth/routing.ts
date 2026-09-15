import type { CurrentUser, SessionMembership } from "@/features/auth/session";
import { stripLocale } from "@/i18n/routing";

const ADMIN_PREFIXES = ["/admin", "/hr"];
const HR_PREFIXES = ["/hr"];
function internalPath(value: string | null): string | null {
  if (!value?.startsWith("/") || value.startsWith("//")) return null;
  try {
    const url = new URL(value, "http://ralion.local");
    return `${stripLocale(url.pathname)}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

export function projectPortalPath(
  projectRole: SessionMembership["project_role"],
  projectId: number,
): string {
  const portal = projectRole === "PM" ? "/product-manager" : "/user";
  return `${portal}?project=${projectId}`;
}

export function defaultLandingPath(user: CurrentUser): string {
  if (user.system_role === "ADMIN") return "/admin";
  if (user.system_role === "HR") return "/hr";
  // Project-scoped users always land on Select Project, even with exactly one
  // active membership — the portal only opens once they explicitly pick it there.
  return "/select-project";
}

export function resolvePostLoginPath(user: CurrentUser, requested: string | null): string {
  const candidate = internalPath(requested);
  if (!candidate) return defaultLandingPath(user);

  const pathname = new URL(candidate, "http://ralion.local").pathname;
  if (user.system_role === "ADMIN") {
    return ADMIN_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
      ? candidate
      : defaultLandingPath(user);
  }
  if (user.system_role === "HR") {
    return HR_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
      ? candidate
      : defaultLandingPath(user);
  }

  // Không khôi phục URL project cũ sau lần đăng nhập mới — luôn đi qua Select Project.
  return defaultLandingPath(user);
}
