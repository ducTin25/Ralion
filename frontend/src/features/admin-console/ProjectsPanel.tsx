"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertIcon,
  ArchiveIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  PlusIcon,
  SearchIcon,
  StarIcon,
  SyncIcon as RestoreIcon,
  XIcon as CloseIcon,
} from "@primer/octicons-react";

import { ConsoleApiError, consoleApi } from "./api";
import { ConsoleAvatar } from "./ConsoleAvatar";
import type {
  ConsoleProject,
  ConsoleProjectDetail,
  MembershipEligibility,
  PageMeta,
  SyncStatus,
} from "./types";

const PAGE_SIZE = 8;
const SEARCH_DEBOUNCE_MS = 300;

const STATUS_TABS = [
  { value: "all", label: "All" },
  { value: "ACTIVE", label: "Active" },
  { value: "ARCHIVED", label: "Archive" },
] as const;

const SYNC_LABEL: Record<SyncStatus, string> = {
  NOT_STARTED: "Not synced",
  SYNCING: "Syncing",
  SUCCESS: "Synced",
  PARTIAL: "Partially synced",
  FAILED: "Sync failed",
};

/* ----------------------------------------------------------------- helpers */

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

/** Dùng chung với các tab khác, xem ConsoleAvatar.tsx. */
function Avatar({ name, size = 26 }: { name: string; size?: number }) {
  return <ConsoleAvatar name={name} size={size} />;
}

function StatusChip({ status }: { status: ConsoleProject["status"] }) {
  return status === "ACTIVE" ? (
    <span className="inline-flex items-center gap-1.5 rounded border border-success-border bg-success-bg px-2 py-0.5 text-[11px] font-semibold text-success-text">
      <span className="h-1.5 w-1.5 rounded-full bg-success" />
      Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded border border-border bg-canvas px-2 py-0.5 text-[11px] font-medium text-text-subtle">
      <span className="h-1.5 w-1.5 rounded-full bg-text-faint" />
      Archive
    </span>
  );
}

/* --------------------------------------------------------- add member dialog */

function AddMemberDialog({
  project,
  onClose,
  onSaved,
}: {
  project: ConsoleProjectDetail;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [eligibility, setEligibility] = useState<MembershipEligibility | null>(null);
  const [userId, setUserId] = useState("");
  const [projectRole, setProjectRole] = useState<"PM" | "ENGINEER">("ENGINEER");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void consoleApi
      .membershipEligibility(project.project_id)
      .then(setEligibility)
      .catch(() => setEligibility({ users: [], projects: [] }));
  }, [project.project_id]);

  const submit = async () => {
    if (!userId) return;
    setSaving(true);
    setError(null);
    try {
      await consoleApi.createMembership({
        user_id: Number(userId),
        project_id: project.project_id,
        project_role: projectRole,
        status: "ACTIVE",
      });
      onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The member could not be added.");
    } finally {
      setSaving(false);
    }
  };

  const noCandidates = eligibility !== null && eligibility.users.length === 0;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b1c30]/30 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Add a member to the project"
        className="w-full max-w-[440px] rounded-md border border-border bg-surface p-6"
      >
        <p className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
          Add member
        </p>
        <h2 className="mt-2 text-lg font-bold text-navy">{project.name}</h2>
        <p className="mt-1 font-mono text-[12px] text-text-subtle">{project.key}</p>

        {noCandidates ? (
          <p className="mt-5 rounded-md border border-warn-border bg-warn-bg p-3 text-[13px] leading-5 text-warn-text">
            No eligible accounts are left. Only active accounts without a system role that are not
            already in this project can be added.
          </p>
        ) : (
          <div className="mt-5 space-y-4">
            <label className="block text-[13px] font-semibold text-text-secondary">
              Members
              <select
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] font-normal outline-none focus:border-link"
              >
                <option value="" disabled>
                  {eligibility ? "Select a member" : "Loading…"}
                </option>
                {eligibility?.users.map((user) => (
                  <option key={user.user_id} value={user.user_id}>
                    {user.display_name} — {user.email}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-[13px] font-semibold text-text-secondary">
              Project role
              <select
                value={projectRole}
                onChange={(event) => setProjectRole(event.target.value as "PM" | "ENGINEER")}
                className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] font-normal outline-none focus:border-link"
              >
                <option value="ENGINEER">Engineer</option>
                <option value="PM">PM</option>
              </select>
            </label>
            {projectRole === "PM" && project.primary_pm_membership_id === null && (
              <p className="rounded-md border border-tint-navy-border bg-tint-navy p-3 text-[12px] leading-5 text-link">
                The project has no PM yet, so this person becomes the primary PM.
              </p>
            )}
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-md border border-danger-border bg-danger-bg p-3 text-[13px] text-danger"
          >
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md border border-border-strong px-4 text-[13px] font-semibold text-navy hover:bg-canvas"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving || !userId || noCandidates}
            onClick={submit}
            className="h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:bg-navy-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Add to project"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------- archive confirmation */

function ArchiveDialog({
  project,
  onClose,
  onConfirm,
}: {
  project: ConsoleProjectDetail;
  onClose: () => void;
  onConfirm: (deactivateMemberships: boolean) => Promise<void>;
}) {
  const [deactivate, setDeactivate] = useState(true);
  const [saving, setSaving] = useState(false);
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-[#0b1c30]/30 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Archive project"
        className="w-full max-w-[440px] rounded-md border border-border bg-surface p-6"
      >
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warn-bg text-warn">
            <AlertIcon />
          </span>
          <div>
            <h2 className="text-[15px] font-bold text-navy">Archive “{project.name}”?</h2>
            <p className="mt-1 text-[13px] leading-5 text-text-subtle">
              An archived project accepts no new memberships and is hidden from project selection.
            </p>
          </div>
        </div>

        {project.active_member_count > 0 && (
          <label className="mt-5 flex cursor-pointer gap-3 rounded-md border border-border bg-canvas p-3">
            <input
              type="checkbox"
              checked={deactivate}
              onChange={(event) => setDeactivate(event.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-[#081534]"
            />
            <span>
              <span className="block text-[13px] font-semibold text-navy">
                Deactivate {project.active_member_count} active memberships
              </span>
              <span className="mt-1 block text-[12px] leading-5 text-text-subtle">
                If you leave this unchecked, members keep their access and the Overview page flags
                it as needing attention.
              </span>
            </span>
          </label>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-md border border-border-strong px-4 text-[13px] font-semibold text-navy hover:bg-canvas"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={async () => {
              setSaving(true);
              try {
                await onConfirm(project.active_member_count > 0 ? deactivate : false);
              } finally {
                setSaving(false);
              }
            }}
            className="h-9 rounded-md border border-danger-border bg-danger-bg px-4 text-[13px] font-semibold text-danger transition hover:bg-surface disabled:opacity-50"
          >
            {saving ? "Saving…" : "Archive project"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ detail drawer */

function ProjectDetailDrawer({
  detail,
  loading,
  error,
  busy,
  onClose,
  onRetry,
  onAddMember,
  onSetPrimaryPm,
  onChangeMember,
  onArchive,
  onRestore,
  onSaveProject,
  savingProject,
}: {
  detail: ConsoleProjectDetail | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  onClose: () => void;
  onRetry: () => void;
  onAddMember: () => void;
  onSetPrimaryPm: (membershipId: number) => void;
  onChangeMember: (membershipId: number, body: Record<string, string>) => void;
  onArchive: () => void;
  onRestore: () => void;
  /** Trả về true khi lưu thành công, để form tự đóng chế độ sửa. */
  onSaveProject: (patch: {
    name: string;
    key: string;
    github_repo: string;
    default_branch: string;
  }) => Promise<boolean>;
  savingProject: boolean;
}) {
  // Lưu project_id đang sửa thay vì cờ boolean: chuyển sang dự án khác thì form tự đóng
  // và không mang theo defaultValue của dự án cũ.
  const [editingFor, setEditingFor] = useState<number | null>(null);
  const editing = detail !== null && editingFor === detail.project_id;
  // `pending/<mã dự án>` là giá trị giả gán lúc tạo dự án, không phải repo thật.
  const hasRepo = Boolean(detail?.github_repo && !detail.github_repo.startsWith("pending/"));
  const setEditing = (value: boolean | ((current: boolean) => boolean)) => {
    const next = typeof value === "function" ? value(editing) : value;
    setEditingFor(next && detail ? detail.project_id : null);
  };
  return (
    <aside
      aria-label="Project details"
      className="flex h-full w-full flex-col overflow-hidden bg-surface"
    >
      {loading && !detail ? (
        <div className="space-y-3 p-6">
          <div className="h-5 w-24 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <div className="h-7 w-56 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft" />
          <div className="h-24 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-md bg-skeleton-soft" />
          <div className="h-40 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded-md bg-skeleton-soft" />
        </div>
      ) : !detail ? (
        <div className="relative flex h-full flex-col items-center justify-center px-6 text-center">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close details"
            className="absolute top-4 right-4 rounded-full p-1.5 text-text-subtle transition hover:bg-canvas hover:text-navy"
          >
            <CloseIcon />
          </button>
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-danger-bg text-danger">
            <AlertIcon />
          </span>
          <p className="mt-3 text-[14px] font-bold text-navy">Details could not be loaded</p>
          <p className="mt-1 text-[12px] leading-5 text-text-subtle">
            {error ?? "The server returned no data for this project."}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition hover:bg-navy-hover"
          >
            Try again
          </button>
        </div>
      ) : (
        <>
          <header className="flex items-start justify-between gap-3 border-b border-divider bg-canvas px-5 py-4">
            <div className="min-w-0">
              <p className="font-mono text-[12px] text-text-subtle">{detail.key}</p>
              <h2 className="mt-1 text-[19px] leading-tight font-bold text-navy">{detail.name}</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusChip status={detail.status} />
                {/* Chỉ sửa được dự án đang hoạt động: dự án đã lưu trữ là bản ghi lịch
                    sử, đổi tên nó khiến mọi tham chiếu cũ không khớp nữa. */}
                {detail.status === "ACTIVE" && (
                  <button
                    type="button"
                    onClick={() => setEditing((value) => !value)}
                    className="rounded-md border border-border-strong px-2.5 py-1 text-[12px] font-semibold text-navy transition hover:bg-surface"
                  >
                    {editing ? "Huỷ sửa" : "Sửa thông tin"}
                  </button>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close details"
              className="shrink-0 rounded-full p-1.5 text-text-subtle transition hover:bg-surface hover:text-navy"
            >
              <CloseIcon />
            </button>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-5">
            {error && (
              <p
                role="alert"
                className="mb-4 rounded-md border border-danger-border bg-danger-bg p-3 text-[13px] text-danger"
              >
                {error}
              </p>
            )}

            {editing && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void onSaveProject({
                    name: String(form.get("name") ?? "").trim(),
                    key: String(form.get("key") ?? "").trim(),
                    github_repo: String(form.get("github_repo") ?? "").trim(),
                    default_branch: String(form.get("default_branch") ?? "").trim() || "main",
                  }).then((ok: boolean) => ok && setEditing(false));
                }}
                className="mb-6 rounded-lg border border-border bg-canvas p-4"
              >
                <h3 className="text-[11px] font-bold tracking-[.08em] uppercase text-text-subtle">
                  Sửa thông tin
                </h3>
                <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                  Tên dự án
                  <input
                    name="name"
                    defaultValue={detail.name}
                    required
                    maxLength={200}
                    className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 text-[13px] font-normal"
                  />
                </label>
                <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                  Mã dự án
                  <input
                    name="key"
                    defaultValue={detail.key}
                    required
                    minLength={2}
                    maxLength={80}
                    pattern="[A-Za-z0-9_-]+"
                    className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 font-mono text-[13px] font-normal"
                  />
                </label>
                {/* Mã dự án hiện khắp nơi trong hệ thống. Đổi nó không hỏng dữ liệu —
                    mọi tham chiếu dùng project_id — nhưng ảnh chụp và tài liệu cũ của
                    nhóm sẽ không khớp nữa, nên nói trước. */}
                <p className="mt-2 text-xs leading-5 text-text-subtle">
                  Đổi mã dự án không ảnh hưởng dữ liệu, nhưng tài liệu và ảnh chụp cũ ghi mã cũ
                  sẽ không còn khớp. Chỉ dùng chữ, số, gạch ngang và gạch dưới.
                </p>

                <div className="mt-4 border-t border-divider pt-4">
                  <label className="block text-[13px] font-semibold text-text-secondary">
                    Repo GitHub
                    <span className="ml-1 font-normal text-text-subtle">
                      (chủ sở hữu / tên repo)
                    </span>
                    <input
                      name="github_repo"
                      // `pending/<key>` là giá trị giả gán lúc tạo dự án. Hiện nó ra như
                      // một tên repo thật sẽ khiến admin tưởng đã cấu hình xong.
                      defaultValue={
                        detail.github_repo && !detail.github_repo.startsWith("pending/")
                          ? detail.github_repo
                          : ""
                      }
                      placeholder="cong-ty/ten-repo"
                      pattern="[^/\s]+/[^/\s]+"
                      className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 font-mono text-[13px] font-normal"
                    />
                  </label>
                  <label className="mt-3 block text-[13px] font-semibold text-text-secondary">
                    Nhánh mặc định
                    <span className="ml-1 font-normal text-text-subtle">(main, master…)</span>
                    <input
                      name="default_branch"
                      defaultValue={detail.default_branch ?? "main"}
                      placeholder="main"
                      className="mt-1.5 h-9 w-full rounded-md border border-border-strong bg-surface px-2.5 font-mono text-[13px] font-normal"
                    />
                  </label>
                  <p className="mt-2 text-xs leading-5 text-text-subtle">
                    Điền dạng <code className="font-mono">chủ-sở-hữu/tên-repo</code>. Tên này sẽ
                    được điền sẵn khi bạn cấp quyền mã nguồn ở tab Cấp quyền truy cập, nên không
                    phải nhớ lại mỗi lần.
                  </p>
                </div>
                <button
                  type="submit"
                  disabled={savingProject}
                  className="mt-4 h-9 w-full rounded-md bg-navy text-[13px] font-bold text-white disabled:opacity-50"
                >
                  {savingProject ? "Đang lưu…" : "Lưu thay đổi"}
                </button>
              </form>
            )}

            {/* PM ownership */}
            <section>
              <h3 className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
                PM in charge
              </h3>
              {detail.primary_pm_name ? (
                <div className="mt-3 flex items-center gap-3 rounded-md border border-border bg-canvas p-3">
                  <Avatar name={detail.primary_pm_name} size={40} />
                  <div className="min-w-0">
                    <p className="truncate text-[14px] font-bold text-navy">
                      {detail.primary_pm_name}
                    </p>
                    <p className="truncate text-[12px] text-text-subtle">
                      {detail.primary_pm_email}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="mt-3 rounded-md border border-warn-border bg-warn-bg p-3">
                  <p className="flex items-center gap-2 text-[13px] font-bold text-warn-text">
                    <AlertIcon />
                    No primary PM
                  </p>
                  <p className="mt-1.5 text-[12px] leading-5 text-warn-text">
                    {detail.active_pm_count > 0
                      ? "The project has PMs but no primary PM. Choose “Set as primary PM” in the list below."
                      : "Add a member with the PM role so someone owns onboarding for this project."}
                  </p>
                </div>
              )}
            </section>

            {/* Members */}
            <section className="mt-6">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-[11px] font-semibold tracking-[.06em] uppercase text-text-subtle">
                  Members ({detail.active_member_count}/{detail.member_count})
                </h3>
                {detail.status === "ACTIVE" && (
                  <button
                    type="button"
                    onClick={onAddMember}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-semibold text-link transition hover:bg-tint-navy"
                  >
                    <PlusIcon />
                    Add
                  </button>
                )}
              </div>

              {detail.members.length === 0 ? (
                <p className="mt-3 text-[13px] text-text-subtle">
                  No members yet — nobody can open this project&apos;s workspace.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {detail.members.map((member) => {
                    const inactive = member.status !== "ACTIVE";
                    return (
                      <li
                        key={member.membership_id}
                        className={`rounded-md border border-border p-3 ${
                          inactive ? "bg-canvas opacity-70" : "bg-surface"
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Avatar name={member.display_name} size={32} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[13px] font-semibold text-navy">
                              {member.display_name}
                            </p>
                            <p className="truncate text-[12px] text-text-subtle">{member.email}</p>
                          </div>
                          {member.is_primary_pm && (
                            <span className="flex shrink-0 items-center gap-1 rounded border border-tint-navy-border bg-tint-navy px-1.5 py-0.5 text-[10px] font-bold text-link">
                              <StarIcon />
                              PRIMARY PM
                            </span>
                          )}
                        </div>
                        <div className="mt-2.5 flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center rounded border border-border bg-canvas px-2 py-0.5 text-[11px] font-bold text-text-muted">
                            {member.project_role === "PM" ? "PM" : "Engineer"}
                          </span>
                          {inactive && (
                            <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[11px] font-semibold text-warn-text">
                              Inactive
                            </span>
                          )}
                          <span className="text-[11px] text-text-subtle">
                            {formatDate(member.joined_at)}
                          </span>
                        </div>
                        {detail.status === "ACTIVE" && (
                          <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-divider pt-2.5">
                            {!inactive && member.project_role === "PM" && !member.is_primary_pm && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => onSetPrimaryPm(member.membership_id)}
                                className="rounded border border-border-strong px-2 py-1 text-[11px] font-semibold text-link transition hover:bg-tint-navy disabled:opacity-50"
                              >
                                Set as primary PM
                              </button>
                            )}
                            {!inactive && member.project_role === "ENGINEER" && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() =>
                                  onChangeMember(member.membership_id, { project_role: "PM" })
                                }
                                className="rounded border border-border-strong px-2 py-1 text-[11px] font-semibold text-link transition hover:bg-tint-navy disabled:opacity-50"
                              >
                                Promote to PM
                              </button>
                            )}
                            {!inactive && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() =>
                                  onChangeMember(member.membership_id, { status: "INACTIVE" })
                                }
                                className="rounded border border-danger-border px-2 py-1 text-[11px] font-semibold text-danger transition hover:bg-danger-bg disabled:opacity-50"
                              >
                                Remove from project
                              </button>
                            )}
                            {inactive && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() =>
                                  onChangeMember(member.membership_id, { status: "ACTIVE" })
                                }
                                className="rounded border border-border-strong px-2 py-1 text-[11px] font-semibold text-link transition hover:bg-tint-navy disabled:opacity-50"
                              >
                                Reactivate
                              </button>
                            )}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {/* Metadata */}
            <section className="mt-6 rounded-md border border-border bg-canvas p-4">
              <dl className="space-y-2.5">
                <div className="flex justify-between gap-3">
                  <dt className="text-[12px] text-text-subtle">Created</dt>
                  <dd className="text-[12px] font-semibold text-navy">
                    {formatDate(detail.created_at)}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[12px] text-text-subtle">Created by</dt>
                  <dd className="text-[12px] font-semibold text-navy">
                    {detail.created_by_name ?? "System"}
                  </dd>
                </div>
                {/* Repo và nhánh phải là HAI dòng riêng. Gộp một dòng ngăn bằng dấu chấm
                    giữa thì "manh/group-project · master" đọc như một nhánh duy nhất —
                    tên repo cũng có dấu gạch chéo giống nhánh kiểu feature/xyz. */}
                <div className="flex justify-between gap-3">
                  <dt className="shrink-0 text-[12px] text-text-subtle">Repo GitHub</dt>
                  <dd className="min-w-0 text-right">
                    {hasRepo ? (
                      <span className="block truncate font-mono text-[12px] font-semibold text-navy">
                        {detail.github_repo}
                      </span>
                    ) : (
                      // Chưa cấu hình repo thì ô ghi chú khi cấp quyền mã nguồn sẽ trống,
                      // nên nói rõ ở đây thay vì để admin tự đoán.
                      <span className="inline-flex items-center rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[11px] font-semibold text-warn-text">
                        Chưa cấu hình
                      </span>
                    )}
                  </dd>
                </div>
                {hasRepo && (
                  <div className="flex justify-between gap-3">
                    <dt className="shrink-0 text-[12px] text-text-subtle">Nhánh mặc định</dt>
                    <dd className="min-w-0 truncate text-right font-mono text-[12px] font-semibold text-navy">
                      {detail.default_branch}
                    </dd>
                  </div>
                )}
                <div className="flex justify-between gap-3">
                  <dt className="text-[12px] text-text-subtle">Sync knowledge</dt>
                  <dd className="text-[12px] font-semibold text-navy">
                    {SYNC_LABEL[detail.sync_status]}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[12px] text-text-subtle">Last synced</dt>
                  <dd className="text-[12px] font-semibold text-navy">
                    {detail.last_synced_at ? formatDate(detail.last_synced_at) : "None"}
                  </dd>
                </div>
              </dl>
            </section>
          </div>

          <footer className="border-t border-divider p-4">
            <button
              type="button"
              disabled={busy}
              onClick={detail.status === "ACTIVE" ? onArchive : onRestore}
              className={`flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-[13px] font-semibold transition disabled:opacity-50 ${
                detail.status === "ACTIVE"
                  ? "border border-border-strong text-navy hover:bg-canvas"
                  : "bg-navy text-white hover:bg-navy-hover"
              }`}
            >
              {detail.status === "ACTIVE" ? <ArchiveIcon /> : <RestoreIcon />}
              {detail.status === "ACTIVE" ? "Archive project" : "Restore project"}
            </button>
          </footer>
        </>
      )}
    </aside>
  );
}

/* -------------------------------------------------------------- main panel */

export function ProjectsPanel({ reloadToken }: { reloadToken: number }) {
  const [rawQuery, setRawQuery] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [pmFilter, setPmFilter] = useState<string>("all");
  const [page, setPage] = useState(1);

  const [rows, setRows] = useState<ConsoleProject[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ConsoleProjectDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [savingProject, setSavingProject] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(rawQuery);
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [rawQuery]);

  const params = useMemo(() => {
    const next = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (query.trim()) next.set("query", query.trim());
    if (statusFilter !== "all") next.set("project_status", statusFilter);
    if (pmFilter !== "all") next.set("pm_state", pmFilter);
    return next;
  }, [page, query, statusFilter, pmFilter]);

  const loadList = useCallback(() => {
    setLoading(true);
    setError(null);
    setErrorStatus(null);
    return consoleApi
      .projects(params)
      .then((result) => {
        setRows(result.items);
        setMeta(result.meta);
      })
      .catch((caught) => {
        setRows([]);
        setMeta(null);
        setErrorStatus(caught instanceof ConsoleApiError ? caught.status : null);
        setError(caught instanceof Error ? caught.message : "Projects could not be loaded.");
      })
      .finally(() => setLoading(false));
  }, [params]);

  useEffect(() => {
    const timer = window.setTimeout(loadList, 0);
    return () => window.clearTimeout(timer);
  }, [loadList, reloadToken]);

  const loadDetail = useCallback((projectId: number) => {
    setDetailLoading(true);
    setDetailError(null);
    return consoleApi
      .projectDetail(projectId)
      .then(setDetail)
      .catch((caught) => {
        setDetail(null);
        setDetailError(
          caught instanceof Error ? caught.message : "Project details could not be loaded.",
        );
      })
      .finally(() => setDetailLoading(false));
  }, []);

  useEffect(() => {
    if (selectedId === null) return;
    const timer = window.setTimeout(() => loadDetail(selectedId), 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, loadDetail]);

  const selectProject = (projectId: number | null) => {
    setSelectedId(projectId);
    setDetail(null);
    setDetailError(null);
  };

  // Every mutation refreshes both panes: the drawer shows the new state and the row
  // behind it keeps its PM / member counts in sync.
  const runMutation = async (action: () => Promise<ConsoleProjectDetail | unknown>) => {
    if (!detail) return;
    setBusy(true);
    setDetailError(null);
    try {
      await action();
      await Promise.all([loadDetail(detail.project_id), loadList()]);
    } catch (caught) {
      setDetailError(
        caught instanceof Error ? caught.message : "The project could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  };

  /** Lưu tên, mã và toạ độ GitHub. Trả về true khi thành công để form tự đóng. */
  const saveProject = async (patch: {
    name: string;
    key: string;
    github_repo: string;
    default_branch: string;
  }) => {
    if (!detail) return false;
    setSavingProject(true);
    setDetailError(null);
    try {
      const updated = await consoleApi.updateProject(detail.project_id, {
        name: patch.name,
        key: patch.key,
      });
      // Repo đi qua endpoint riêng của nhóm TV1. Gọi TUẦN TỰ và chỉ khi giá trị thật sự
      // đổi: chạy song song thì hai request cùng ghi vào một hàng Project và bản ghi
      // thắng cuộc sẽ ghi đè bản kia.
      const currentRepo = detail.github_repo?.startsWith("pending/") ? "" : (detail.github_repo ?? "");
      if (patch.github_repo && (patch.github_repo !== currentRepo || patch.default_branch !== detail.default_branch)) {
        setDetail(
          await consoleApi.connectGithubRepo(
            detail.project_id,
            patch.github_repo,
            patch.default_branch,
          ),
        );
        await loadDetail(detail.project_id);
      } else {
        setDetail(updated);
      }
      loadList();
      return true;
    } catch (caught) {
      setDetailError(caught instanceof Error ? caught.message : "Không lưu được thông tin dự án.");
      return false;
    } finally {
      setSavingProject(false);
    }
  };

  const totalPages = meta ? Math.max(1, Math.ceil(meta.total / PAGE_SIZE)) : 1;
  const drawerOpen = selectedId !== null;

  return (
    <div className="console-projects">
      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface p-2.5">
        <label className="relative min-w-[220px] flex-1 sm:max-w-[300px]">
          <span className="sr-only">Search projects</span>
          <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-faint">
            <SearchIcon />
          </span>
          <input
            value={rawQuery}
            onChange={(event) => setRawQuery(event.target.value)}
            placeholder="Search name or project key…"
            className="h-9 w-full rounded-md border border-border-strong bg-surface pr-3 pl-9 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
          />
        </label>
        <div className="flex gap-1.5">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => {
                setStatusFilter(tab.value);
                setPage(1);
              }}
              className={`rounded-md px-3 py-1.5 text-[12px] font-semibold transition ${
                statusFilter === tab.value
                  ? "bg-tint-navy text-link ring-1 ring-tint-navy-border"
                  : "border border-border-strong text-text-subtle hover:bg-canvas"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {/* Dự án chạy mà không có PM là vấn đề nghiêm trọng nhất, và đang được đếm ở
            trang tổng quan — nên phải lọc riêng ra được. */}
        <select
          value={pmFilter}
          onChange={(event) => {
            setPmFilter(event.target.value);
            setPage(1);
          }}
          className="h-9 cursor-pointer rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none transition focus:border-link focus:ring-2 focus:ring-tint-navy"
        >
          <option value="all">PM phụ trách: Tất cả</option>
          <option value="MISSING">Chưa có PM</option>
          <option value="ASSIGNED">Đã có PM</option>
        </select>
      </div>

      <div
        className={`grid gap-4 ${drawerOpen ? "xl:grid-cols-[minmax(0,1fr)_400px]" : "grid-cols-1"}`}
      >
        {/* Table */}
        <div className="flex min-w-0 flex-col overflow-hidden rounded-md border border-border bg-surface">
          {loading && (
            <div className="space-y-2 p-3">
              {Array.from({ length: 6 }, (_, index) => (
                <div
                  key={index}
                  className="h-12 animate-[project-skeleton_1.5s_ease-in-out_infinite] rounded bg-skeleton-soft"
                />
              ))}
            </div>
          )}

          {!loading && error && (
            <div role="alert" className="p-8 text-center">
              <p className="text-[15px] font-bold text-danger">
                {errorStatus === 401 || errorStatus === 403
                  ? "This session does not have Admin rights"
                  : "Data could not be loaded"}
              </p>
              <p className="mt-1 text-[13px] text-text-subtle">{error}</p>
              <button
                type="button"
                onClick={loadList}
                className="mt-4 h-9 rounded-md bg-navy px-4 text-[13px] font-semibold text-white"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && rows.length === 0 && (
            <p className="px-6 py-16 text-center text-[13px] text-text-subtle">
              No projects match the current filters.
            </p>
          )}

          {!loading && !error && rows.length > 0 && (
            <div className="min-w-0 flex-1 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <thead>
                  <tr>
                    {[
                      "Dự án",
                      "Trạng thái",
                      "PM phụ trách",
                      "Thành viên",
                      "Ngày tạo",
                    ].map(
                      (header) => (
                        <th
                          key={header}
                          className="text-[11px] font-bold tracking-[.07em] uppercase text-text-subtle"
                        >
                          {header}
                        </th>
                      ),
                    )}
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-divider">
                  {rows.map((project) => {
                    const selected = project.project_id === selectedId;
                    const archived = project.status === "ARCHIVED";
                    return (
                        <tr
                          key={project.project_id}
                          tabIndex={0}
                          aria-label={`View details for ${project.name}`}
                          onClick={() => selectProject(selected ? null : project.project_id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              selectProject(selected ? null : project.project_id);
                            }
                          }}
                        aria-selected={selected}
                        className={`group cursor-pointer transition-colors ${
                          selected ? "row-selected" : ""
                        }`}
                      >
                        <td
                          className={`border-l-2 ${selected ? "border-l-link" : "border-l-transparent"} ${
                            archived ? "opacity-60" : ""
                          }`}
                        >
                          <p className="font-bold text-navy">{project.name}</p>
                          <p className="mt-0.5 font-mono text-[11px] text-text-subtle">
                            {project.key}
                          </p>
                        </td>
                        <td>
                          <StatusChip status={project.status} />
                        </td>
                        <td className={archived ? "opacity-60" : ""}>
                          {project.primary_pm_name ? (
                            <span className="flex items-center gap-2">
                              <Avatar name={project.primary_pm_name} />
                              <span className="text-navy">{project.primary_pm_name}</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 rounded border border-warn-border bg-warn-bg px-2 py-0.5 text-[11px] font-semibold text-warn-text">
                              <AlertIcon />
                              No PM assigned
                            </span>
                          )}
                        </td>
                        <td className={archived ? "opacity-60" : ""}>
                          <span className="font-semibold text-navy tabular-nums">
                            {project.active_member_count}
                          </span>
                          {project.member_count > project.active_member_count && (
                            <span className="text-[11px] text-text-subtle tabular-nums">
                              {" "}
                              / {project.member_count}
                            </span>
                          )}
                        </td>
                        <td className={`text-text-subtle ${archived ? "opacity-60" : ""}`}>
                          {formatDate(project.created_at)}
                        </td>
                        <td className="text-right">
                          <span
                            className={`inline-flex text-text-faint transition-opacity ${
                              selected
                                ? "text-link opacity-100"
                                : "opacity-0 group-hover:opacity-100"
                            }`}
                          >
                            <ChevronRightIcon />
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!loading && !error && meta && meta.total > 0 && (
            <footer className="console-table-footer flex items-center justify-between gap-3 px-4 py-3">
              <p className="text-[12px] text-text-subtle">
                Page {page} of {totalPages}
                <span className="mx-2 text-border-strong">·</span>
                {rows.length} of {meta.total} projects
              </p>
              <div className="flex gap-1">
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={page === 1}
                  onClick={() => setPage((current) => current - 1)}
                  className="pager-console flex h-8 w-8 items-center justify-center px-0"
                >
                  <ChevronLeftIcon />
                </button>
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                  className="pager-console flex h-8 w-8 items-center justify-center px-0"
                >
                  <ChevronRightIcon />
                </button>
              </div>
            </footer>
          )}
        </div>

        {/* Detail drawer */}
        {drawerOpen && (
          <>
            <div
              role="presentation"
              onClick={() => selectProject(null)}
              className="fixed inset-0 z-40 bg-[#0b1c30]/25 xl:hidden"
            />
            <div className="fixed inset-y-0 right-0 z-40 w-full max-w-[400px] xl:static xl:z-auto xl:max-w-none">
              <div className="h-full border-l border-border xl:sticky xl:top-4 xl:h-[calc(100vh-9rem)] xl:overflow-hidden xl:rounded-md xl:border">
                <ProjectDetailDrawer
                  detail={detail}
                  loading={detailLoading}
                  error={detailError}
                  busy={busy}
                  onClose={() => selectProject(null)}
                  onRetry={() => selectedId !== null && loadDetail(selectedId)}
                  onAddMember={() => setAddingMember(true)}
                  onSetPrimaryPm={(membershipId) =>
                    void runMutation(() =>
                      consoleApi.setPrimaryPm(detail!.project_id, membershipId),
                    )
                  }
                  onChangeMember={(membershipId, body) =>
                    void runMutation(() => consoleApi.updateMembership(membershipId, body))
                  }
                  onArchive={() => setArchiving(true)}
                  onRestore={() =>
                    void runMutation(() =>
                      consoleApi.changeProjectStatus(detail!.project_id, "ACTIVE"),
                    )
                  }
                  onSaveProject={saveProject}
                  savingProject={savingProject}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {addingMember && detail && (
        <AddMemberDialog
          project={detail}
          onClose={() => setAddingMember(false)}
          onSaved={() => {
            void loadDetail(detail.project_id);
            void loadList();
          }}
        />
      )}

      {archiving && detail && (
        <ArchiveDialog
          project={detail}
          onClose={() => setArchiving(false)}
          onConfirm={async (deactivateMemberships) => {
            await runMutation(() =>
              consoleApi.changeProjectStatus(detail.project_id, "ARCHIVED", deactivateMemberships),
            );
            setArchiving(false);
          }}
        />
      )}
    </div>
  );
}
