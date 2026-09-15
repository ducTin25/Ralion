"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Pause, Play } from "lucide-react";

import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";
import {
  extractMarkdownOutline,
  renderMarkdown,
} from "@/features/project-management/components/ui/markdownPreview";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import {
  formatDate,
  STATUS_LABEL_KEYS,
} from "@/features/member-onboarding/components/memberPortalUi";
import type { MemberTaskDetail } from "@/features/member-onboarding/types";

import styles from "./MemberPortal.module.scss";

type DetailTab = "content" | "documents" | "citations" | "dependencies";

type PreviewTarget = {
  title: string;
  url: string;
  section: string | null;
  snippet: string | null;
};

type TaskDetailPageProps = {
  task: MemberTaskDetail;
  onBack: () => void;
  onTransition: (status: "IN_PROGRESS" | "DONE") => void;
  onReportBlocker: () => void;
  updating: boolean;
  actionError: string | null;
};

const DETAIL_TABS: DetailTab[] = ["content", "documents", "citations", "dependencies"];

function parseBackendTimestamp(value: string | null): number | null {
  if (!value) return null;
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`).getTime();
  return Number.isNaN(parsed) ? null : parsed;
}

export function TaskDetailPage({
  task,
  onBack,
  onTransition,
  onReportBlocker,
  updating,
  actionError,
}: TaskDetailPageProps) {
  const t = useTranslations("member.taskDetail");
  const memberT = useTranslations("member");
  const locale = useLocale();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const citations = task.citations ?? [];
  const citationCount = citations.length || task.sources.length;
  const outline = useMemo(() => extractMarkdownOutline(task.instruction), [task.instruction]);
  const [activeTab, setActiveTab] = useState<DetailTab>("content");
  const [activeSection, setActiveSection] = useState<string>(outline[0]?.id ?? "");
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [timerPaused, setTimerPaused] = useState(false);
  const [pausedAt, setPausedAt] = useState<number | null>(null);
  const [pausedTotal, setPausedTotal] = useState(0);

  useEffect(() => {
    if (task.status !== "IN_PROGRESS" || timerPaused) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [task.status, timerPaused]);

  useEffect(() => {
    if (task.status !== "IN_PROGRESS") return;
    const saved = window.sessionStorage.getItem(`member-task-timer-${task.plan_task_id}`);
    if (!saved) return;
    try {
      const state = JSON.parse(saved) as {
        paused: boolean;
        pausedAt: number | null;
        pausedTotal: number;
      };
      const hydrateTimer = window.setTimeout(() => {
        setTimerPaused(state.paused);
        setPausedAt(state.pausedAt);
        setPausedTotal(state.pausedTotal);
      }, 0);
      return () => window.clearTimeout(hydrateTimer);
    } catch {
      window.sessionStorage.removeItem(`member-task-timer-${task.plan_task_id}`);
    }
  }, [task.plan_task_id, task.status]);

  const formatDuration = (milliseconds: number) => {
    const totalMinutes = Math.max(0, Math.floor(Math.abs(milliseconds) / 60_000));
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    if (days > 0) return t("durationDays", { days, hours });
    return t("durationHours", { hours, minutes });
  };
  const formatCountdownClock = (milliseconds: number) => {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1_000));
    const hours = Math.floor(totalSeconds / 3_600);
    const minutes = Math.floor((totalSeconds % 3_600) / 60);
    const seconds = totalSeconds % 60;
    return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
  };
  const dueTime = parseBackendTimestamp(task.due_at);
  const startedTime = parseBackendTimestamp(task.started_at);
  const currentPauseDuration = timerPaused && pausedAt !== null ? now - pausedAt : 0;
  const remainingTaskTime =
    startedTime === null
      ? null
      : task.estimated_minutes * 60_000 - (now - startedTime - pausedTotal - currentPauseDuration);

  const toggleTimer = () => {
    const currentTime = Date.now();
    if (timerPaused) {
      const nextPausedTotal = pausedTotal + (pausedAt === null ? 0 : currentTime - pausedAt);
      setPausedTotal(nextPausedTotal);
      setPausedAt(null);
      setTimerPaused(false);
      setNow(currentTime);
      window.sessionStorage.setItem(
        `member-task-timer-${task.plan_task_id}`,
        JSON.stringify({ paused: false, pausedAt: null, pausedTotal: nextPausedTotal }),
      );
      return;
    }
    setPausedAt(currentTime);
    setTimerPaused(true);
    setNow(currentTime);
    window.sessionStorage.setItem(
      `member-task-timer-${task.plan_task_id}`,
      JSON.stringify({ paused: true, pausedAt: currentTime, pausedTotal }),
    );
  };

  useEffect(() => {
    if (activeTab !== "content" || outline.length === 0) return;
    if (!("IntersectionObserver" in window)) return;

    const headings = outline
      .map((heading) => document.getElementById(heading.id))
      .filter((heading): heading is HTMLElement => heading !== null);
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const next = visible[0]?.target.id;
        if (next) setActiveSection(next);
      },
      { rootMargin: "-18% 0px -68% 0px", threshold: [0, 1] },
    );

    headings.forEach((heading) => observer.observe(heading));
    return () => observer.disconnect();
  }, [activeTab, outline]);

  const scrollToSection = (id: string) => {
    const target = document.getElementById(id);
    if (!target) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    setActiveSection(id);
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % DETAIL_TABS.length;
    if (event.key === "ArrowLeft")
      nextIndex = (index - 1 + DETAIL_TABS.length) % DETAIL_TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = DETAIL_TABS.length - 1;
    if (nextIndex === null) return;

    event.preventDefault();
    const nextTab = DETAIL_TABS[nextIndex];
    setActiveTab(nextTab);
    tabRefs.current[nextIndex]?.focus();
  };

  const openCitation = (index: number) => {
    const citation = citations[index - 1];
    if (citation) {
      setPreview({
        title: citation.document_title,
        url: citation.document_url,
        section: citation.section_path,
        snippet: citation.content_snippet,
      });
      return;
    }
    const source = task.sources[index - 1];
    if (source) {
      setPreview({ title: source.title, url: source.source_url, section: null, snippet: null });
    }
  };

  const renderPrimaryAction = () => {
    if (task.status === "NOT_STARTED") {
      return (
        <button
          type="button"
          className={styles.primaryButton}
          disabled={!task.can_start || updating}
          onClick={() => onTransition("IN_PROGRESS")}
        >
          {updating ? t("saving") : t("startTask")}
        </button>
      );
    }
    if (task.status === "IN_PROGRESS") {
      return (
        <button
          type="button"
          className={styles.primaryButton}
          disabled={!task.can_complete || updating}
          onClick={() => onTransition("DONE")}
        >
          <MemberIcon name="check" size={15} />
          {updating ? t("saving") : t("markDone")}
        </button>
      );
    }
    return null;
  };

  const renderActionButtons = () => (
    <div className={styles.taskActionButtons} role="group" aria-label={t("actions")}>
      {task.status !== "DONE" && (
        <button
          type="button"
          className={styles.dangerButton}
          onClick={onReportBlocker}
          disabled={updating}
        >
          <MemberIcon name="flag" size={15} /> {t("reportBlocked")}
        </button>
      )}
      {renderPrimaryAction()}
    </div>
  );

  const tabs = [
    { key: "content" as const, icon: "check", label: t("tabContent"), count: null },
    {
      key: "documents" as const,
      icon: "document",
      label: t("tabDocuments"),
      count: task.sources.length,
    },
    {
      key: "citations" as const,
      icon: "search",
      label: t("tabCitations"),
      count: citations.length,
    },
    {
      key: "dependencies" as const,
      icon: "lock",
      label: t("tabDependencies"),
      count: task.dependencies.length,
    },
  ] as const;

  const panelId = `task-${task.plan_task_id}-${activeTab}-panel`;

  return (
    <div
      className={styles.taskPage}
      role="region"
      aria-label={task.title}
      data-complete={task.status === "DONE"}
    >
      <header className={styles.taskPageHeader}>
        <button type="button" className={styles.backButton} onClick={onBack}>
          <MemberIcon name="back" size={16} /> {t("backToChecklist")}
        </button>

        <div className={styles.taskHeadingRow}>
          <span className={styles.taskOrderBadge}>{task.display_order}</span>
          <div className={styles.taskHeadingCopy}>
            {task.mandatory && <b className={styles.requiredBadge}>{t("required")}</b>}
            <h1>{task.title}</h1>
            <div className={styles.taskFacts}>
              <span className={`${styles.statusPill} ${styles[`status${task.status}`]}`}>
                {task.status === "DONE" && <MemberIcon name="check" size={14} />}
                {memberT(STATUS_LABEL_KEYS[task.status])}
              </span>
              <span>
                <MemberIcon name="clock" size={14} />{" "}
                {t("minutes", { count: task.estimated_minutes })}
              </span>
              <span>{t("due", { date: formatDate(task.due_at, locale) ?? "—" })}</span>
              <span>
                <MemberIcon name="document" size={14} />{" "}
                {t("documentsCount", { count: task.sources.length })}
              </span>
              {task.status !== "DONE" && dueTime !== null && (
                <span
                  className={
                    task.is_overdue
                      ? styles.taskDeadlineOverdue
                      : task.is_due_soon
                        ? styles.taskDeadlineSoon
                        : undefined
                  }
                >
                  <MemberIcon name={task.is_overdue ? "bell" : "clock"} size={14} />
                  {task.is_overdue
                    ? t("overdueBy", { time: formatDuration(now - dueTime) })
                    : t("dueIn", { time: formatDuration(dueTime - now) })}
                </span>
              )}
            </div>
          </div>
        </div>

        {task.objective && (
          <div className={styles.objectiveCard}>
            <span className={styles.objectiveIcon} aria-hidden="true">
              <MemberIcon name="arrow" size={16} />
            </span>
            <div>
              <b>{t("objective")}</b>
              <p>{task.objective}</p>
            </div>
          </div>
        )}

        <div className={styles.headerActionStatus} role={actionError ? "alert" : undefined}>
          {actionError ? (
            <span className={styles.actionError}>{actionError}</span>
          ) : task.status === "DONE" ? (
            <span className={styles.actionSuccess}>
              <MemberIcon name="check" size={14} /> {t("completed")}
            </span>
          ) : (
            <span>{task.lock_reason ?? t("progressHint")}</span>
          )}
        </div>
      </header>

      {task.is_locked && task.lock_reason && (
        <div className={styles.lockNotice}>
          <MemberIcon name="lock" size={16} />
          <div>
            <b>{t("locked")}</b>
            <span>{task.lock_reason}</span>
          </div>
        </div>
      )}

      <nav className={styles.detailTabs} role="tablist" aria-label={t("details")}>
        {tabs.map(({ key, icon, label, count }, index) => (
          <button
            key={key}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            id={`task-${task.plan_task_id}-${key}-tab`}
            type="button"
            role="tab"
            className={activeTab === key ? styles.detailTabActive : undefined}
            aria-selected={activeTab === key}
            aria-controls={`task-${task.plan_task_id}-${key}-panel`}
            tabIndex={activeTab === key ? 0 : -1}
            onClick={() => setActiveTab(key)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
          >
            <MemberIcon name={icon} size={15} /> {label}
            {count !== null && <span>{count}</span>}
          </button>
        ))}
        {task.status === "IN_PROGRESS" && remainingTaskTime !== null && (
          <div className={styles.taskTimerControl} aria-live="polite">
            <span className={styles.liveTaskTime}>
              <MemberIcon name="clock" size={14} />
              {locale.startsWith("vi") ? "Còn lại" : "Time left"}{" "}
              {formatCountdownClock(remainingTaskTime)}
            </span>
            <button type="button" className={styles.timerToggle} onClick={toggleTimer}>
              {timerPaused ? (
                <Play aria-hidden="true" size={15} strokeWidth={2.2} />
              ) : (
                <Pause aria-hidden="true" size={15} strokeWidth={2.2} />
              )}
              {timerPaused
                ? locale.startsWith("vi")
                  ? "Tiếp tục"
                  : "Resume"
                : locale.startsWith("vi")
                  ? "Tạm dừng"
                  : "Pause"}
            </button>
          </div>
        )}
      </nav>

      {activeTab === "content" && outline.length > 0 && (
        <label className={styles.mobileOutlineSelect}>
          <span>{t("goToSection")}</span>
          <select value={activeSection} onChange={(event) => scrollToSection(event.target.value)}>
            {outline.map((heading) => (
              <option key={heading.id} value={heading.id}>
                {heading.level === 3 ? `— ${heading.text}` : heading.text}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className={styles.readingWorkspace}>
        <section
          id={panelId}
          className={styles.detailPanel}
          role="tabpanel"
          aria-labelledby={`task-${task.plan_task_id}-${activeTab}-tab`}
          tabIndex={0}
        >
          {activeTab === "content" && (
            <article className={styles.taskContent}>
              <div className={styles.markdownContent}>
                {renderMarkdown(task.instruction, {
                  citationCount,
                  onCitationClick: openCitation,
                })}
              </div>
            </article>
          )}

          {activeTab === "documents" && (
            <div className={styles.detailGrid}>
              {task.sources.length ? (
                task.sources.map((source) => (
                  <button
                    key={source.version_id}
                    type="button"
                    className={styles.detailCard}
                    onClick={() =>
                      setPreview({
                        title: source.title,
                        url: source.source_url,
                        section: null,
                        snippet: null,
                      })
                    }
                  >
                    <span className={styles.detailCardIcon}>
                      <MemberIcon name="document" size={17} />
                    </span>
                    <span>
                      <b>{source.title}</b>
                      <small>{source.citation_note ?? t("readWholeDocument")}</small>
                    </span>
                    <MemberIcon name="arrow" size={15} />
                  </button>
                ))
              ) : (
                <p className={styles.emptyDetail}>{t("noSourceDocuments")}</p>
              )}
            </div>
          )}

          {activeTab === "citations" && (
            <div className={styles.detailGrid}>
              {citations.length ? (
                citations.map((citation) => (
                  <button
                    key={citation.citation_id}
                    type="button"
                    className={styles.detailCard}
                    onClick={() =>
                      setPreview({
                        title: citation.document_title,
                        url: citation.document_url,
                        section: citation.section_path,
                        snippet: citation.content_snippet,
                      })
                    }
                  >
                    <span className={styles.citationBadge}>{citation.citation_order}</span>
                    <span>
                      <b>
                        {citation.citation_note ?? citation.section_path ?? citation.document_title}
                      </b>
                      <small>{citation.document_title}</small>
                    </span>
                    <MemberIcon name="arrow" size={15} />
                  </button>
                ))
              ) : (
                <p className={styles.emptyDetail}>{t("noCitations")}</p>
              )}
            </div>
          )}

          {activeTab === "dependencies" && (
            <div className={styles.detailGrid}>
              {task.dependencies.length ? (
                task.dependencies.map((dependency) => (
                  <div key={dependency.plan_task_id} className={styles.dependencyCard}>
                    <span
                      className={
                        dependency.status === "DONE"
                          ? styles.dependencyDone
                          : styles.dependencyPending
                      }
                    >
                      <MemberIcon
                        name={dependency.status === "DONE" ? "check" : "clock"}
                        size={14}
                      />
                    </span>
                    <span>
                      <b>{dependency.title}</b>
                      <small>{memberT(STATUS_LABEL_KEYS[dependency.status])}</small>
                    </span>
                  </div>
                ))
              ) : (
                <p className={styles.emptyDetail}>{t("noDependencies")}</p>
              )}
            </div>
          )}
        </section>

        <aside className={styles.readingRail} aria-label={t("readingTools")}>
          {activeTab === "content" && outline.length > 0 && (
            <nav className={styles.outlineCard} aria-label={t("onThisPage")}>
              <b>{t("onThisPage")}</b>
              <ol>
                {outline.map((heading) => (
                  <li key={heading.id} data-level={heading.level}>
                    <button
                      type="button"
                      aria-current={activeSection === heading.id ? "location" : undefined}
                      onClick={() => scrollToSection(heading.id)}
                    >
                      {heading.text}
                    </button>
                  </li>
                ))}
              </ol>
            </nav>
          )}

          <div className={styles.railActionCard} data-complete={task.status === "DONE"}>
            <div className={styles.railStatus}>
              <span className={`${styles.statusPill} ${styles[`status${task.status}`]}`}>
                {task.status === "DONE" && <MemberIcon name="check" size={14} />}
                {memberT(STATUS_LABEL_KEYS[task.status])}
              </span>
              <small>{task.lock_reason ?? t("progressHint")}</small>
            </div>
            {task.status !== "DONE" && renderActionButtons()}
          </div>
        </aside>
      </div>

      {preview && (
        <DocumentPreviewModal
          title={preview.title}
          sourceUrl={preview.url}
          highlightSection={preview.section}
          highlightSnippet={preview.snippet}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
