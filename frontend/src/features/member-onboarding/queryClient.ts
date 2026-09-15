import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

export const memberQueryKeys = {
  root: ["member-onboarding"] as const,
  projects: () => [...memberQueryKeys.root, "projects"] as const,
  checklist: (projectId: number) => [...memberQueryKeys.root, "checklist", projectId] as const,
  blockers: (projectId: number) => [...memberQueryKeys.root, "blockers", projectId] as const,
  task: (taskId: number) => [...memberQueryKeys.root, "task", taskId] as const,
  notifications: (projectId: number) =>
    [...memberQueryKeys.root, "notifications", projectId] as const,
};

function shouldRetry(failureCount: number, error: unknown) {
  if (!(error instanceof ApiError)) return false;
  const transient = error.status === 408 || error.status === 429 || error.status >= 500;
  return transient && failureCount < 2;
}

export function createMemberQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 5 * 60_000,
        retry: shouldRetry,
        retryDelay: (attempt) => Math.min(500 * 2 ** attempt, 2_000),
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}
