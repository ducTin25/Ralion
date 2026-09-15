"use client";

import { useCallback, useEffect, useState } from "react";

import { AUTH_ENDPOINT } from "@/lib/api";

export type SessionMembership = {
  membership_id: number;
  project_id: number;
  project_name: string;
  project_key: string;
  project_role: "PM" | "ENGINEER";
  status: "ACTIVE" | "INACTIVE";
  project_status: "ACTIVE" | "ARCHIVED";
};

export type ResponseLength = "CONCISE" | "STANDARD" | "DETAILED";
export type ResponseTone = "NEUTRAL" | "GUIDE" | "MENTOR" | "BUDDY";

export type CurrentUser = {
  user_id: number;
  display_name: string;
  email: string;
  system_role: "ADMIN" | "HR" | null;
  status: "ACTIVE" | "INACTIVE";
  response_length: ResponseLength;
  response_tone: ResponseTone;
  memberships: SessionMembership[];
  expires_at: string | null;
};

export type LoginResult = {
  user_id: number;
  redirect_to: string | null;
  outcome: string;
  expires_at: string | null;
};

export class SessionError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "SessionError";
  }
}

/**
 * Mọi request đều gửi cookie. Header X-User-Id vẫn được đính kèm khi có giá trị
 * trong localStorage để không phá luồng dev cũ, nhưng backend luôn ưu tiên cookie.
 */
export function authHeaders(): HeadersInit {
  const stored =
    typeof window === "undefined"
      ? null
      : window.localStorage.getItem("ralion-demo-user-id")?.trim();
  return stored && /^\d+$/.test(stored) ? { "X-User-Id": stored } : {};
}

async function authRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${AUTH_ENDPOINT}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new SessionError(
      body?.detail?.message ?? body?.detail ?? "The session could not be read.",
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export const authApi = {
  login: (body: { email: string; password: string }) =>
    authRequest<LoginResult>("/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => authRequest<CurrentUser>("/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    authRequest<{ outcome: string }>("/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  refresh: () => authRequest<CurrentUser>("/refresh", { method: "POST" }),
  logout: () => authRequest<{ outcome: string }>("/logout", { method: "POST" }),
  updatePreferences: (body: { response_length?: ResponseLength; response_tone?: ResponseTone }) =>
    authRequest<CurrentUser>("/me/preferences", { method: "PATCH", body: JSON.stringify(body) }),
};

/** Đăng xuất dùng chung cho các shell không sở hữu useSession riêng. */
export async function signOutCurrentSession() {
  try {
    await authApi.logout();
  } catch {
    // Logout phía client vẫn phải hoàn tất khi backend mất kết nối hoặc phiên đã hết hạn.
  } finally {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("ralion-demo-user-id");
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
  }
}

/** Gia hạn khi phiên còn dưới ngưỡng này. Backend cấp TTL 30 phút. */
const REFRESH_MARGIN_MS = 5 * 60 * 1000;
const REFRESH_CHECK_INTERVAL_MS = 60 * 1000;

export function useSession() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<SessionError | null>(null);

  const load = useCallback(
    () =>
      authApi
        .me()
        .then((profile) => {
          setUser(profile);
          setError(null);
        })
        .catch((caught) => {
          setUser(null);
          setError(caught instanceof SessionError ? caught : null);
        })
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  // Gia hạn khi phiên sắp hết hạn và tab đang mở, để người dùng đang làm việc
  // không bị đá ra giữa chừng. Tab ẩn thì bỏ qua, hết hạn là đúng mong đợi.
  useEffect(() => {
    if (!user?.expires_at) return;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      const remaining = new Date(user.expires_at as string).getTime() - Date.now();
      if (remaining > REFRESH_MARGIN_MS) return;
      void authApi
        .refresh()
        .then(setUser)
        .catch(() => setUser(null));
    }, REFRESH_CHECK_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [user]);

  const signOut = useCallback(async () => {
    // signOutCurrentSession navigates to /login itself; don't set state here — a
    // setUser(null) re-render before that navigation lands is what flashes the
    // "cannot verify session" fallback in every shell that reads `user`.
    await signOutCurrentSession();
  }, []);

  // Reuses the session's own state instead of a separate "preferences" store — the response
  // already carries the full updated CurrentUserDTO, so no refetch is needed.
  const updatePreferences = useCallback(
    (body: { response_length?: ResponseLength; response_tone?: ResponseTone }) =>
      authApi.updatePreferences(body).then((updated) => {
        setUser(updated);
        return updated;
      }),
    [],
  );

  return { user, loading, error, reload: load, signOut, updatePreferences };
}
