"use client";

import { useSearchParams } from "next/navigation";

import { usePathname, useRouter } from "@/i18n/navigation";
import { shallowNavigate } from "@/lib/shallowNavigation";
import { useCallback } from "react";

import type { TaskCategory } from "@/features/member-onboarding/types";

export type MemberPortalView =
  "overview" | "tasks" | "notifications" | "chat" | "policy" | "conventions" | "blockers";

type PortalUrlUpdate = {
  projectId?: number | null;
  view?: MemberPortalView;
  taskId?: number | null;
  category?: TaskCategory | null;
};

function positiveInteger(value: string | null) {
  if (!value || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export function buildMemberPortalHref(
  pathname: string,
  current: URLSearchParams | Readonly<URLSearchParams>,
  update: PortalUrlUpdate,
) {
  const next = new URLSearchParams(current.toString());
  if (update.projectId !== undefined) {
    if (update.projectId === null) next.delete("project");
    else next.set("project", String(update.projectId));
  }
  if (update.view !== undefined) {
    if (update.view === "overview") next.delete("view");
    else next.set("view", update.view);
  }
  if (update.taskId !== undefined) {
    if (update.taskId === null) next.delete("task");
    else next.set("task", String(update.taskId));
  }
  if (update.view === "tasks" && update.taskId) next.delete("view");
  if (update.category !== undefined) {
    if (update.category === null) next.delete("category");
    else next.set("category", update.category);
  }
  if (update.projectId !== undefined) next.delete("task");
  if (
    update.view === "blockers" ||
    update.view === "conventions" ||
    update.view === "chat" ||
    update.view === "policy"
  ) {
    next.delete("task");
    next.delete("category");
  }
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function useMemberPortalUrl() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = positiveInteger(searchParams.get("project"));
  const taskId = positiveInteger(searchParams.get("task"));
  const categoryValue = searchParams.get("category");
  const category: TaskCategory | null =
    categoryValue === "COMPANY" ||
    categoryValue === "ORIENTATION" ||
    categoryValue === "ACCESS" ||
    categoryValue === "SETUP" ||
    categoryValue === "CODEBASE" ||
    categoryValue === "CONVENTION"
      ? categoryValue
      : null;
  const view: MemberPortalView =
    searchParams.get("view") === "blockers"
      ? "blockers"
      : searchParams.get("view") === "chat"
        ? "chat"
        : searchParams.get("view") === "policy"
          ? "policy"
          : searchParams.get("view") === "conventions"
            ? "conventions"
            : searchParams.get("view") === "notifications"
              ? "notifications"
              : searchParams.get("view") === "tasks" || taskId !== null
                ? "tasks"
                : "overview";

  const href = useCallback(
    (update: PortalUrlUpdate) => buildMemberPortalHref(pathname, searchParams, update),
    [pathname, searchParams],
  );
  const navigate = useCallback(
    (update: PortalUrlUpdate, replace = false) => {
      const next = href(update);
      if (shallowNavigate(next, replace)) return;
      if (replace) router.replace(next, { scroll: false });
      else router.push(next, { scroll: false });
    },
    [href, router],
  );

  return { projectId, taskId, category, view, href, navigate };
}
