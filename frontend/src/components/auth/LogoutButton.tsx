"use client";

import { useState, type ReactNode } from "react";

import { signOutCurrentSession } from "@/features/auth/session";

type LogoutButtonProps = {
  className?: string;
  children?: ReactNode;
};

export function LogoutButton({ className, children = "Sign out" }: LogoutButtonProps) {
  const [pending, setPending] = useState(false);

  return (
    <button
      type="button"
      className={className}
      disabled={pending}
      onClick={() => {
        setPending(true);
        void signOutCurrentSession();
      }}
    >
      {pending ? "Signing out…" : children}
    </button>
  );
}
