import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { cloneElement, isValidElement, useId } from "react";

import styles from "./PmField.module.scss";

export function PmField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  const generatedId = useId();
  const isDirectControl =
    isValidElement(children) &&
    (children.type === PmInput ||
      children.type === PmSelect ||
      children.type === PmTextarea ||
      children.type === "input" ||
      children.type === "select" ||
      children.type === "textarea");
  const controlId = htmlFor ?? (isDirectControl ? generatedId : undefined);
  const labelledChild =
    isDirectControl && isValidElement<{ id?: string }>(children)
      ? cloneElement(children, { id: children.props.id ?? controlId })
      : children;

  return (
    <div className={styles.field}>
      <label htmlFor={controlId}>{label}</label>
      {labelledChild}
    </div>
  );
}

export function PmInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${styles.input} ${props.className ?? ""}`} />;
}

export function PmSelect(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${styles.select} ${props.className ?? ""}`} />;
}

export function PmTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${styles.textarea} ${props.className ?? ""}`} />;
}

export function PmErrorText({ children }: { children: ReactNode }) {
  return <p className={styles.errorText}>{children}</p>;
}
