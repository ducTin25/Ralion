import type { CSSProperties } from "react";

type RalionBrandProps = {
  size?: number;
  tone?: "brand" | "inverse";
  label?: string;
  subtitle?: string;
  markOnly?: boolean;
  className?: string;
  markClassName?: string;
  wordmarkClassName?: string;
  href?: string | null;
};

/** Shared, dependency-free Ralion SVG lockup for app chrome and compact surfaces. */
export function RalionBrand({
  size = 20,
  tone = "brand",
  label = "Ralion",
  className,
  markOnly = false,
  markClassName,
  wordmarkClassName,
  href = null,
}: RalionBrandProps) {
  const splitAt = Math.min(3, label.length);
  const brand = (
    <span
      className={["ralion-brand", className].filter(Boolean).join(" ")}
      data-tone={tone}
      aria-label={markOnly ? label : undefined}
      style={{ "--ralion-brand-size": `${size}px` } as CSSProperties}
    >
      <svg
        aria-hidden="true"
        className={["ralion-brand-mark", markClassName].filter(Boolean).join(" ")}
        viewBox="0 0 32 32"
        focusable="false"
      >
        <rect width="28" height="28" x="2" y="2" rx="8" fill="currentColor" />
        <path
          d="M10 23V9h6.2c3.7 0 6 2 6 5.2 0 2.2-1.1 3.9-3 4.7L23 23h-4.2l-3.2-3.6h-2V23H10Zm3.6-6.6H16c1.7 0 2.7-.8 2.7-2.1 0-1.4-1-2.1-2.7-2.1h-2.4v4.2Z"
          fill="white"
        />
      </svg>
      {!markOnly && (
        <strong className={["ralion-brand-wordmark", wordmarkClassName].filter(Boolean).join(" ")}>
          {label.slice(0, splitAt)}
          <span>{label.slice(splitAt)}</span>
        </strong>
      )}
    </span>
  );

  if (!href) return brand;

  return (
    <a aria-label={`${label} — Home`} className="ralion-brand-link" href={href}>
      {brand}
    </a>
  );
}
