"use client";

import type { ComponentProps, MouseEvent } from "react";

import { Link } from "@/i18n/navigation";
import { canShallowNavigate, shallowNavigate } from "@/lib/shallowNavigation";

type ShallowSearchLinkProps = Omit<ComponentProps<typeof Link>, "href"> & {
  href: string;
};

/** A normal localized link that becomes a no-RSC History API update on the same page. */
export function ShallowSearchLink({ href, onClick, ...props }: ShallowSearchLinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      props.target === "_blank" ||
      !canShallowNavigate(href)
    ) {
      return;
    }

    event.preventDefault();
    shallowNavigate(href);
  }

  return <Link {...props} href={href} prefetch={false} onClick={handleClick} />;
}
