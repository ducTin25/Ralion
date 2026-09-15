"use client";

import { useCallback, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getProjectDocumentContent, updatePlanTask } from "@/features/project-management/api";
import { getMemberPolicyContent } from "@/features/member-onboarding/api";
import type {
  PlanTaskCitationResponseDTO,
  PlanTaskResponseDTO,
  PlanTaskSourceResponseDTO,
} from "@/features/project-management/dto/responseDTO/planTask.response";
import { PmIcon } from "@/features/project-management/components/PmIconSprite";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { CATEGORY_OPTIONS } from "@/features/project-management/components/template/TaskFormModal";
import { PmButton } from "@/features/project-management/components/ui/PmButton";
import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";
import { PmDrawer } from "@/features/project-management/components/ui/PmDrawer";
import {
  PmErrorText,
  PmField,
  PmInput,
  PmTextarea,
} from "@/features/project-management/components/ui/PmField";
import { PmPill, PmTag } from "@/features/project-management/components/ui/PmPill";
import { pmToast } from "@/features/project-management/components/ui/PmToast";
import { extractMarkdownOutline, renderMarkdown } from "@/features/project-management/components/ui/markdownPreview";

import styles from "./PlanTaskDrawer.module.scss";

type PlanTaskDrawerProps = {
  task: PlanTaskResponseDTO;
  projectId: number;
  editable: boolean;
  onClose: () => void;
  onSaved: (task: PlanTaskResponseDTO) => void;
  presentation?: "drawer" | "page";
  allTasks?: PlanTaskResponseDTO[];
  onSelectTask?: (task: PlanTaskResponseDTO) => void;
};

function formatDate(value: string | null, locale: string): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(locale === "vi" ? "vi-VN" : "en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
  });
}

/** Thứ modal xem trước cần, gom từ 2 nguồn có hình dạng khác nhau: trích dẫn (mức đoạn, có snippet
 * để nhảy đúng chỗ) và tài liệu nguồn (mức file, chỉ mở từ đầu). */
type PreviewTarget = {
  documentId: number;
  title: string;
  url: string;
  section: string | null;
  snippet: string | null;
};

function targetFromCitation(citation: PlanTaskCitationResponseDTO): PreviewTarget {
  return {
    documentId: citation.document_id,
    title: citation.document_title,
    url: citation.document_url,
    section: citation.section_path,
    snippet: citation.content_snippet,
  };
}

function targetFromSource(source: PlanTaskSourceResponseDTO): PreviewTarget {
  return {
    documentId: source.document_id,
    title: source.document_title,
    url: source.document_url,
    // Nguồn mức tài liệu không có đoạn cụ thể để dò -> chỉ còn cách nhảy theo tiêu đề (nếu có).
    section: source.section_path,
    snippet: null,
  };
}

/** Chi tiết 1 task trong Candidate Plan: hướng dẫn (markdown do AI sinh theo khung cố định:
 * Mục tiêu / Các bước thực hiện / Kết quả cần đạt), danh sách tài liệu nguồn bấm xem được, và chỗ
 * PM sửa tay khi plan còn Nháp. */
export function PlanTaskDrawer({
  task,
  projectId,
  editable,
  onClose,
  onSaved,
  presentation = "drawer",
  allTasks = [],
  onSelectTask,
}: PlanTaskDrawerProps) {
  const t = useTranslations("pmUi");
  const locale = useLocale();
  const [activeTab, setActiveTab] = useState<"task" | "documents" | "citations">("task");
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [instruction, setInstruction] = useState(task.instruction);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewTarget | null>(null);
  const previewDocumentId = preview?.documentId ?? null;
  const loadPreviewContent = useCallback(async () => {
    if (previewDocumentId === null) return "";
    try {
      const detail = await getProjectDocumentContent(projectId, previewDocumentId);
      return detail.content;
    } catch {
      // Task PM có thể trích cả POLICY dùng chung công ty. Endpoint project chỉ nhận domain PROJECT;
      // fallback sang endpoint policy đã có sẵn để vẫn mở toàn văn, không cần thay đổi backend.
      const policy = await getMemberPolicyContent(previewDocumentId);
      return policy.content;
    }
  }, [projectId, previewDocumentId]);
  const contentRef = useRef<HTMLDivElement>(null);
  const taskScrollRef = useRef<HTMLElement>(null);
  const [expandedCategory, setExpandedCategory] = useState<PlanTaskResponseDTO["category"] | null>(task.category);
  const [activeOutlineIndex, setActiveOutlineIndex] = useState(0);
  const outline = extractMarkdownOutline(task.instruction);

  // Plan sinh trước khi có bảng citation không có `citations` -> `[n]` lùi về map theo `sources` như
  // hành vi cũ, thay vì thành nút bấm chết.
  const citationTargets = task.citations.length > 0 ? task.citations : null;
  // `citation_order` là khóa thật của số `[n]` trong instruction. Không dùng vị trí mảng vì danh sách
  // có thể không liên tục (ví dụ chỉ có order 1, 7, 19); khi đó `[19]` vẫn phải bấm được.
  const citationCount = citationTargets
    ? Math.max(...citationTargets.map((citation) => citation.citation_order), 0)
    : task.sources.length;

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePlanTask(task.plan_task_id, { title, instruction });
      onSaved(updated);
      setEditing(false);
      pmToast(t("taskSaved"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  const drawer = (
    <>
      <PmDrawer
        variant={presentation === "page" ? "page" : "workspace"}
        eyebrow={
          <div className={styles.eyebrow}>
            <PmTag>{t("taskNumber", { number: task.display_order })}</PmTag>
            {task.mandatory && <PmPill variant="neutral">{t("required")}</PmPill>}
            {task.sources.length === 0 && <PmPill variant="warning">{t("missingSources")}</PmPill>}
          </div>
        }
        title={<span className={styles.taskTitleHeading}><span><PmIcon name="check-circle" size={20} /></span>{task.title}</span>}
        onClose={onClose}
        footer={
          <div className={styles.footerBar}>
            <PmButton size="sm" onClick={onClose}>
              {t("close")}
            </PmButton>
            {editable ? (
              editing ? (
                <div className={styles.footerActions}>
                  <PmButton
                    onClick={() => {
                      setTitle(task.title);
                      setInstruction(task.instruction);
                      setEditing(false);
                      setError(null);
                    }}
                    disabled={saving}
                  >
                    {t("cancel")}
                  </PmButton>
                  <PmButton variant="primary" onClick={handleSave} disabled={saving}>
                    {saving ? t("saving") : t("saveChanges")}
                  </PmButton>
                </div>
              ) : (
                <PmButton
                  size="sm"
                  className={styles.editBtn}
                  onClick={() => {
                    setActiveTab("task");
                    setEditing(true);
                  }}
                >
                  <PmIcon name="pencil" size={13} />
                  {t("editTaskContent")}
                </PmButton>
              )
            ) : (
              <p className={styles.readOnlyNote}>{t("approvedReadOnly")}</p>
            )}
          </div>
        }
      >
        <div className={styles.metaRow}>
          <span>
            <PmIcon name="flag" size={12} /> {t("minutes", { count: task.estimated_minutes })}
          </span>
          <span>
            <PmIcon name="check-circle" size={12} />{" "}
            {t("dueDate", { date: formatDate(task.due_at, locale) })}
          </span>
          <span>
            <PmIcon name="doc" size={12} /> {t("documentCount", { count: task.sources.length })}
          </span>
        </div>

        <div className={styles.tabs} role="tablist" aria-label={t("taskDetails")}>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "task"}
            className={activeTab === "task" ? styles.activeTab : ""}
            onClick={() => setActiveTab("task")}
          >
            <PmIcon name="check-circle" size={15} /> {t("taskContent")}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "documents"}
            className={activeTab === "documents" ? styles.activeTab : ""}
            onClick={() => setActiveTab("documents")}
          >
            <PmIcon name="doc" size={15} /> {t("documents")} <span>{task.sources.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "citations"}
            className={activeTab === "citations" ? styles.activeTab : ""}
            onClick={() => setActiveTab("citations")}
          >
            <PmIcon name="eye" size={15} /> {t("passageCitations")}{" "}
            <span>{task.citations.length}</span>
          </button>
        </div>

        <div className={styles.contentLayout}>
        <div className={styles.tabContent} ref={contentRef}>
          {activeTab === "task" &&
            (editing ? (
              <div className={styles.editForm}>
                <PmField label={t("taskName")}>
                  <PmInput value={title} onChange={(e) => setTitle(e.target.value)} />
                </PmField>
                <PmField label={t("instructionsMarkdown")}>
                  <PmTextarea
                    rows={18}
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                  />
                </PmField>
                <p className={styles.editHint}>{t("instructionStructureHint")}</p>
                {error && <PmErrorText>{error}</PmErrorText>}
              </div>
            ) : (
              <div className={styles.instruction}>
                {/* Trích dẫn `[n]` trong nội dung khớp `citation_order`, mỗi số là 1 ĐOẠN cụ thể — bấm
                vào mở tài liệu và cuộn thẳng tới đúng đoạn đó. */}
                {renderMarkdown(task.instruction, {
                  citationCount,
                  headingPrefix: (_text, level) =>
                    level === 2 ? (
                      <span className={`${styles.groupIcon} ${styles.iconaccent}`}>
                        <PmIcon name="check-circle" size={13} />
                      </span>
                    ) : null,
                  onCitationClick: (index) => {
                    const citation = citationTargets?.find(
                      (candidate) => candidate.citation_order === index,
                    );
                    if (citation) return setPreview(targetFromCitation(citation));
                    const source = task.sources[index - 1];
                    if (source) setPreview(targetFromSource(source));
                  },
                })}
              </div>
            ))}

          {activeTab === "documents" && (
            <div className={styles.sourceBlock}>
              <div className={styles.panelHeading}>
                <div>
                  <span>{t("requiredChecklist")}</span>
                  <h4>{t("documentsToRead")}</h4>
                  <p>{t("selectDocumentHelp")}</p>
                </div>
                <b>{t("documentCount", { count: task.sources.length })}</b>
              </div>
              <p className={styles.sourceTitle}>
                {t("sourceDocumentsCount", { count: task.sources.length })}
              </p>
              {task.sources.length === 0 ? (
                <p className={styles.emptyNote}>{t("noSourceDocumentsBody")}</p>
              ) : (
                task.sources.map((source) => (
                  <button
                    key={source.task_source_id}
                    type="button"
                    className={styles.sourceRow}
                    onClick={() => setPreview(targetFromSource(source))}
                  >
                    <span className={styles.sourceIcon}>
                      <PmIcon name="doc" size={13} />
                    </span>
                    <span className={styles.sourceBody}>
                      <b>{source.document_title}</b>
                      {source.citation_note && <span>{source.citation_note}</span>}
                    </span>
                    <PmIcon name="eye" size={13} className={styles.sourceEye} />
                  </button>
                ))
              )}
            </div>
          )}

          {/* Danh sách trích dẫn tách riêng khối tài liệu ở trên: 1 tài liệu có thể góp nhiều mục, ở
            đây liệt kê từng mục kèm số `[n]` để đối chiếu nhanh với nội dung. */}
          {activeTab === "citations" && (
            <div className={styles.sourceBlock}>
              <div className={styles.panelHeading}>
                <div>
                  <span>{t("verifiedSources")}</span>
                  <h4>{t("passageCitations")}</h4>
                  <p>{t("citationHelp")}</p>
                </div>
                <b>{t("passageCount", { count: task.citations.length })}</b>
              </div>
              <p className={styles.sourceTitle}>
                {t("passageCitationsCount", { count: task.citations.length })}
              </p>
              {task.citations.length === 0 ? (
                <p className={styles.emptyNote}>{t("noPassageCitations")}</p>
              ) : (
                task.citations.map((citation) => (
                  <button
                    key={citation.citation_id}
                    type="button"
                    className={styles.sourceRow}
                    onClick={() => setPreview(targetFromCitation(citation))}
                  >
                    <span className={styles.citationIndex}>{citation.citation_order}</span>
                    <span className={styles.sourceBody}>
                      <b>{citation.citation_note ?? citation.document_title}</b>
                      <span>{citation.document_title}</span>
                    </span>
                    <PmIcon name="eye" size={13} className={styles.sourceEye} />
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        {activeTab === "task" && !editing && (
          <aside className={styles.taskOutline}>
            <h4>{locale === "vi" ? "Trong task này" : "In this task"}</h4>
            <nav aria-label={locale === "vi" ? "Mục lục task" : "Task outline"}>
              {outline.map((section, index) => {
                return (
                  <button
                    key={section.id}
                    type="button"
                    className={`${index === activeOutlineIndex ? styles.outlineActive : ""} ${section.level === 3 ? styles.outlineNested : ""}`}
                    onClick={() => {
                      const headings = contentRef.current?.querySelectorAll("h2, h3");
                      headings?.[index]?.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}
                  >
                    {section.text}
                  </button>
                );
              })}
            </nav>
            <div className={styles.outlineStatus}>
              <PmIcon name={editable ? "pencil" : "check2"} size={15} />
              <b>{editable ? (locale === "vi" ? "Có thể chỉnh sửa" : "Editable") : (locale === "vi" ? "Đã phê duyệt" : "Approved")}</b>
              <span>{locale === "vi" ? "Xem và kiểm tra nội dung task trước khi phát hành." : "Review the task content before publishing."}</span>
            </div>
          </aside>
        )}
        </div>
      </PmDrawer>

      {preview && (
        <DocumentPreviewModal
          title={preview.title}
          sourceUrl={preview.url}
          fetchContent={loadPreviewContent}
          highlightSnippet={preview.snippet}
          highlightSection={preview.section}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );

  if (presentation !== "page") return drawer;

  return (
    <div className={styles.taskWorkspace}>
      <aside className={styles.journeySidebar}>
        <div className={styles.journeyBrand}><RalionBrand size={27} /></div>
        <button type="button" className={styles.backToPlan} onClick={onClose}>
          <PmIcon name="arrow" size={14} />
          {locale === "vi" ? "Quay lại kế hoạch" : "Back to plan"}
        </button>
        <div className={styles.journeyTitle}>
          <b>{locale === "vi" ? "Lộ trình onboarding" : "Onboarding journey"}</b>
          <span>{allTasks.length} {locale === "vi" ? "nhiệm vụ" : "tasks"}</span>
        </div>
        <nav className={styles.journeyNav}>
          {CATEGORY_OPTIONS.map((category) => {
            const groupTasks = allTasks.filter((item) => item.category === category.value);
            if (groupTasks.length === 0) return null;
            return (
              <section key={category.value} data-active={groupTasks.some((item) => item.plan_task_id === task.plan_task_id)}>
                <button
                  type="button"
                  className={styles.journeySectionToggle}
                  aria-expanded={expandedCategory === category.value}
                  onClick={() => setExpandedCategory((current) => current === category.value ? null : category.value)}
                >
                  <span className={styles.journeyCategoryIcon} data-variant={category.variant}><PmIcon name={category.icon} size={15} /></span>
                  <div><b>{t(category.labelKey)}</b><small>{groupTasks.length} task</small></div>
                  <PmIcon name="chevron-down" size={14} className={styles.journeyChevron} />
                </button>
                {expandedCategory === category.value && <div>
                  {groupTasks.map((item) => (
                    <button type="button" key={item.plan_task_id} data-current={item.plan_task_id === task.plan_task_id} onClick={() => {
                      setExpandedCategory(item.category);
                      setActiveOutlineIndex(0);
                      taskScrollRef.current?.scrollTo({ top: 0, behavior: "smooth" });
                      onSelectTask?.(item);
                    }}>
                      <span>{item.display_order}</span>{item.title}
                    </button>
                  ))}
                </div>}
              </section>
            );
          })}
        </nav>
      </aside>
      <main
        className={styles.taskPageScroll}
        ref={taskScrollRef}
        onScroll={() => {
          const headings = contentRef.current?.querySelectorAll("h2, h3");
          if (!headings?.length) return;
          let current = 0;
          headings.forEach((heading, index) => {
            if (heading.getBoundingClientRect().top <= 150) current = index;
          });
          setActiveOutlineIndex(current);
        }}
      >{drawer}</main>
    </div>
  );
}
