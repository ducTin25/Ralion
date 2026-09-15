"use client";

import { useEffect, useState } from "react";

import styles from "./PmToast.module.scss";

type ToastListener = (message: string) => void;
let listeners: ToastListener[] = [];

/** Gọi từ bất kỳ đâu trong module PM để hiện toast xác nhận — thay cho alert(). */
export function pmToast(message: string) {
  listeners.forEach((listener) => listener(message));
}

/** Mount đúng 1 lần trong PmShell — chỗ hiển thị toast thật. */
export function PmToastHost() {
  const [toasts, setToasts] = useState<{ id: number; message: string }[]>([]);

  useEffect(() => {
    const listener: ToastListener = (message) => {
      const id = Date.now() + Math.random();
      setToasts((prev) => [...prev, { id, message }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 2800);
    };
    listeners.push(listener);
    return () => {
      listeners = listeners.filter((l) => l !== listener);
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className={styles.wrap}>
      {toasts.map((t) => (
        <div key={t.id} className={styles.toast}>
          {t.message}
        </div>
      ))}
    </div>
  );
}
