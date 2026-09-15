import { Link } from "@/i18n/navigation";
import type { ReactNode } from "react";

type BrandHomeLinkProps = {
  className?: string;
  children: ReactNode;
  onClick?: () => void;
};

/**
 * Wraps a shell's existing brand mark so the logo behaves the same way in every
 * authenticated workspace: click → Landing Page. One shared behavior instead of
 * each shell (PM/Member/HR/Admin) reimplementing its own click handler.
 */
export function BrandHomeLink({ className, children, onClick }: BrandHomeLinkProps) {
  return (
    <Link href="/" aria-label="Ralion" className={className} onClick={onClick}>
      {children}
    </Link>
  );
}
