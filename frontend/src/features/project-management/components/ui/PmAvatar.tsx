import { avatarColorFor, initialsFor } from "./avatarColor";
import styles from "./PmAvatar.module.scss";

type PmAvatarProps = {
  seed: string;
  label: string;
  size?: "sm" | "md" | "lg";
};

/** Avatar vuông màu cố định theo hash(seed) — dùng chung cho cả User và Project, không cần ảnh thật. */
export function PmAvatar({ seed, label, size = "sm" }: PmAvatarProps) {
  return (
    <div
      className={`${styles.avatar} ${styles[size]}`}
      style={{ background: avatarColorFor(seed) }}
    >
      {initialsFor(label)}
    </div>
  );
}
