import type { ButtonHTMLAttributes, ReactNode } from "react";

import styles from "./PmButton.module.scss";

type PmButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost" | "danger";
  size?: "default" | "sm";
  children: ReactNode;
};

export function PmButton({
  variant = "default",
  size = "default",
  className,
  children,
  ...rest
}: PmButtonProps) {
  const classes = [
    styles.btn,
    variant === "primary" && styles.primary,
    variant === "ghost" && styles.ghost,
    variant === "danger" && styles.danger,
    size === "sm" && styles.sm,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={classes} {...rest}>
      {children}
    </button>
  );
}
