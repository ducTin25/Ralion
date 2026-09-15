"use client";

import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/features/auth/session";
import { PolicyAccountMenu } from "@/features/policy-acknowledgement/PolicyAccountMenu";
import { Link } from "@/i18n/navigation";

import { myAccessApi, type MyAccessGrant } from "./api";

const formatDateTime = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : null;

function waitingLabel(hours: number | null) {
  if (hours === null) return "";
  if (hours < 1) return "vừa gửi";
  if (hours < 24) return `đã chờ ${Math.round(hours)} giờ`;
  return `đã chờ ${Math.floor(hours / 24)} ngày`;
}

function GrantCard({ grant }: { grant: MyAccessGrant }) {
  const granted = grant.status === "GRANTED";
  return (
    <li
      className={`rounded-xl border bg-white p-4 ${
        grant.is_overdue ? "border-[#e3bcbb]" : "border-border"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[15px] font-bold text-navy">{grant.resource_label}</p>
          <p className="mt-0.5 text-xs text-text-subtle">
            {grant.project_name ?? "—"}
            {grant.project_key && <span className="ml-1.5">· {grant.project_key}</span>}
          </p>
          {grant.resource_note && (
            <p className="mt-1.5 font-mono text-[12px] text-text-subtle">{grant.resource_note}</p>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold ${
            granted
              ? "border-[#bcd9c6] bg-[#f2f9f4] text-[#1f7a4d]"
              : grant.is_overdue
                ? "border-[#e3bcbb] bg-[#fdf3f3] text-[#8f2f2d]"
                : "border-border bg-canvas text-text-subtle"
          }`}
        >
          {granted ? "Đã có quyền" : "Đang chờ cấp"}
        </span>
      </div>

      <p className="mt-3 text-xs leading-5 text-text-subtle">
        {granted ? (
          <>
            Cấp lúc {formatDateTime(grant.granted_at)}
            {grant.granted_by_name && <> bởi {grant.granted_by_name}</>}.
          </>
        ) : (
          <>
            Yêu cầu tạo lúc {formatDateTime(grant.requested_at)}, {waitingLabel(grant.waiting_hours)}
            . Quản trị viên sẽ xử lý — bạn không cần làm gì thêm.
          </>
        )}
      </p>
    </li>
  );
}

/**
 * "Quyền truy cập của tôi" — màn hình cho kỹ sư.
 *
 * Thay cho việc nhắn Slack hỏi mò "quyền repo của em xong chưa". Chỉ đọc: kỹ sư không
 * tự cấp hay tự thu hồi quyền của mình được, và yêu cầu do hệ thống tự sinh khi admin
 * gán vào dự án nên ở đây cũng không có nút "xin quyền".
 */
export function MyAccessScreen() {
  const [items, setItems] = useState<MyAccessGrant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user: sessionUser } = useSession();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems((await myAccessApi.list()).items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không tải được danh sách quyền.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Hoãn sang macrotask: gọi thẳng thì setState chạy đồng bộ trong effect và React
    // cảnh báo cascading render.
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const pending = items.filter((item) => item.status === "REQUESTED");
  const granted = items.filter((item) => item.status === "GRANTED");

  return (
    <main className="ralion-console min-h-screen bg-canvas text-text">
      {/* Trang này mở được trực tiếp qua URL nên phải tự có danh tính và đường thoát. */}
      <header className="flex h-[64px] items-center justify-between border-b border-header-border bg-white px-5 md:px-8">
        <Link href="/user" className="text-sm font-semibold text-link hover:underline">
          ← Về không gian làm việc
        </Link>
        <PolicyAccountMenu
          displayName={sessionUser?.display_name}
          roleLabel="Kỹ sư tham gia dự án"
        />
      </header>

      <div className="mx-auto max-w-[900px] px-5 py-9 md:px-8">
        <p className="text-[11px] font-bold tracking-[.12em] text-[#4f5f96]">TÀI KHOẢN</p>
        <h1 className="mt-2 text-[28px] font-bold tracking-[-.035em] text-navy">
          Quyền truy cập của tôi
        </h1>
        <p className="mt-2 max-w-[640px] text-sm leading-6 text-text-subtle">
          Danh sách quyền bạn cần cho công việc, do quản trị viên cấp. Yêu cầu được tạo tự động khi
          bạn được thêm vào dự án — bạn không phải tự xin.
        </p>

        {loading ? (
          <div className="mt-7 space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="h-24 animate-pulse rounded-xl bg-[#f0f2f8]" />
            ))}
          </div>
        ) : error ? (
          <div className="mt-7 rounded-2xl border border-border bg-white p-10 text-center">
            <p role="alert" className="text-sm text-[#8f2f2d]">
              {error}
            </p>
            <button
              type="button"
              onClick={() => void load()}
              className="mt-4 h-10 rounded-lg bg-navy px-5 text-sm font-bold text-white"
            >
              Thử lại
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="mt-7 rounded-2xl border border-border bg-white p-12 text-center">
            <h2 className="text-lg font-bold text-navy">Chưa có quyền nào được theo dõi</h2>
            <p className="mx-auto mt-2 max-w-[420px] text-sm leading-6 text-text-subtle">
              Danh sách sẽ xuất hiện khi bạn được thêm vào một dự án đang hoạt động.
            </p>
          </div>
        ) : (
          <div className="mt-7 space-y-7">
            {pending.length > 0 && (
              <section>
                <h2 className="text-sm font-bold text-navy">Đang chờ cấp ({pending.length})</h2>
                <ul className="mt-3 space-y-3">
                  {pending.map((grant) => (
                    <GrantCard key={grant.grant_id} grant={grant} />
                  ))}
                </ul>
              </section>
            )}
            {granted.length > 0 && (
              <section>
                <h2 className="text-sm font-bold text-navy">Đã có quyền ({granted.length})</h2>
                <ul className="mt-3 space-y-3">
                  {granted.map((grant) => (
                    <GrantCard key={grant.grant_id} grant={grant} />
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
