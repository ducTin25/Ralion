"use client";

import { useCallback, useEffect, useState } from "react";

import { authHeaders } from "@/features/auth/session";
import { ACTIVE_MEMBERSHIP_ENDPOINT, MEMBERSHIPS_ENDPOINT } from "@/lib/api";
import type { ActiveMembershipResponse, MembershipCard } from "@/types/project";

export class MembershipApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "MembershipApiError";
  }
}

async function parseError(response: Response): Promise<MembershipApiError> {
  const body = (await response.json().catch(() => null)) as {
    detail?: { code?: string; message?: string } | string;
  } | null;
  const detail = body?.detail;
  const code = typeof detail === "object" && detail?.code ? detail.code : "SYSTEM_ERROR";
  const message =
    typeof detail === "object" && detail?.message
      ? detail.message
      : typeof detail === "string"
        ? detail
        : "Your active projects could not be loaded.";
  return new MembershipApiError(code, message, response.status);
}

export function useProjectMemberships(enabled = true) {
  const [data, setData] = useState<MembershipCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<MembershipApiError | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const refetch = useCallback(() => setRequestVersion((version) => version + 1), []);

  useEffect(() => {
    if (!enabled) return;

    const controller = new AbortController();
    async function loadMemberships() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(MEMBERSHIPS_ENDPOINT, {
          credentials: "include",
          headers: authHeaders(),
          signal: controller.signal,
        });
        if (!response.ok) throw await parseError(response);
        setData((await response.json()) as MembershipCard[]);
      } catch (caught) {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof MembershipApiError
            ? caught
            : new MembershipApiError(
                "SYSTEM_ERROR",
                "Your active projects could not be loaded.",
                503,
              ),
        );
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }
    void loadMemberships();
    return () => controller.abort();
  }, [enabled, requestVersion]);

  const establishMembership = useCallback(async (membershipId: number) => {
    const response = await fetch(ACTIVE_MEMBERSHIP_ENDPOINT, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ membership_id: membershipId }),
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as ActiveMembershipResponse;
  }, []);

  return { data, isLoading, error, refetch, establishMembership };
}
