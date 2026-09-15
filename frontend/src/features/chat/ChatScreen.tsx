"use client";

import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";

import { BrandHomeLink } from "@/components/brand/BrandHomeLink";
import { RalionBrand } from "@/components/brand/RalionBrand";
import { LanguageSwitcher } from "@/components/i18n/LanguageSwitcher";
import { MobileNavDrawer } from "@/components/navigation/MobileNavDrawer";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api";
import { askChat } from "@/features/chat/api";
import { useConversation } from "@/features/chat/hooks/useConversation";
import { SafeMarkdown } from "@/features/chat/SafeMarkdown";
import { useSession } from "@/features/auth/session";
import type { CurrentUser } from "@/features/auth/session";
import { AccountChatPreferences } from "@/features/auth/AccountChatPreferences";
import { MemberIcon } from "@/features/member-onboarding/components/MemberIcon";
import { MemberSidebar } from "@/features/member-onboarding/components/MemberSidebar";
import { usePersistentTheme } from "@/features/member-onboarding/hooks/usePersistentTheme";
import portalStyles from "@/features/member-onboarding/components/MemberPortal.module.scss";
import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";
import { useProjectMemberships } from "@/features/project-selection/hooks/useProjectMemberships";
import { useEmbeddingWarmup } from "@/hooks/useEmbeddingWarmup";
import type { ChatCitation, ChatClaim, ChatGuidance, ChatPrompt, ChatScope } from "@/types/chat";

import styles from "./ChatScreen.module.scss";

function citationLabel(citation: ChatCitation, fallback: string) {
  return citation.source_title || citation.section_heading || fallback;
}

function uniqueCitations(citations: ChatCitation[]) {
  return citations.filter(
    (citation, index) =>
      citations.findIndex(
        (item) => item.chunk_id === citation.chunk_id && item.quote === citation.quote,
      ) === index,
  );
}

function isSelectedCitation(selected: ChatCitation | null, citation: ChatCitation) {
  return selected?.chunk_id === citation.chunk_id && selected.quote === citation.quote;
}

function AssistantMessage({ children }: { children: ReactNode }) {
  return <article className={styles.assistantMessage}>{children}</article>;
}

function ScopeSelector({
  scope,
  memberships,
  loading,
  onChange,
}: {
  scope: ChatScope;
  memberships: ReturnType<typeof useProjectMemberships>["data"];
  loading: boolean;
  onChange: (scope: ChatScope) => void;
}) {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div className={styles.scopeSelector} ref={rootRef}>
      <button
        type="button"
        className={`${styles.scopeTrigger} ${scope.type === "POLICY" ? styles.policyScope : styles.projectScope}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <MemberIcon name={scope.type === "POLICY" ? "document" : "lock"} size={15} />
        <span>
          {scope.type === "POLICY"
            ? t("companyPolicy")
            : t("projectScope", { name: scope.projectName })}
        </span>
        <span className={styles.scopeChevron} aria-hidden="true">
          <MemberIcon name="chevronDown" size={14} />
        </span>
      </button>
      {open && (
        <div className={styles.scopeMenu} role="listbox" aria-label={t("askWithin")}>
          <p>{t("companyKnowledge")}</p>
          <button
            type="button"
            role="option"
            aria-selected={scope.type === "POLICY"}
            onClick={() => {
              onChange({ type: "POLICY" });
              setOpen(false);
            }}
          >
            <span className={styles.policyIcon}>
              <MemberIcon name="document" size={15} />
            </span>
            <span>
              <b>{t("companyPolicy")}</b>
              <small>{t("companyGuidance")}</small>
            </span>
            {scope.type === "POLICY" && <span className={styles.checkmark}>✓</span>}
          </button>
          {(memberships.length > 0 || loading) && (
            <p className={styles.projectsLabel}>{t("yourProjects")}</p>
          )}
          {loading && <span className={styles.menuStatus}>{t("loadingProjects")}</span>}
          {!loading &&
            memberships.map((membership) => {
              const selected =
                scope.type === "PROJECT" && scope.membershipId === membership.membershipId;
              return (
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  key={membership.membershipId}
                  onClick={() => {
                    onChange({
                      type: "PROJECT",
                      membershipId: membership.membershipId,
                      projectName: membership.projectName,
                      projectKey: membership.projectKey,
                    });
                    setOpen(false);
                  }}
                >
                  <span className={styles.projectIcon}>{membership.projectKey.slice(0, 2)}</span>
                  <span>
                    <b>{membership.projectName}</b>
                    <small>{t("projectKnowledge")}</small>
                  </span>
                  {selected && <span className={styles.checkmark}>✓</span>}
                </button>
              );
            })}
        </div>
      )}
    </div>
  );
}

function CitationReferences({
  citations,
  selectedCitation,
  onSelect,
  claimIndex,
  ariaLabel,
}: {
  citations: ChatCitation[];
  selectedCitation: ChatCitation | null;
  onSelect: (citation: ChatCitation) => void;
  claimIndex?: number;
  ariaLabel?: string;
}) {
  const t = useTranslations("chat");
  const sources = uniqueCitations(citations);
  if (sources.length === 0) return null;
  return (
    <div
      className={styles.citations}
      aria-label={ariaLabel ?? t("sourcesForClaim", { count: (claimIndex ?? 0) + 1 })}
    >
      {sources.map((citation, citationIndex) => (
        <button
          type="button"
          key={`${citation.chunk_id}-${citationIndex}-${citation.quote}`}
          className={`${styles.citationChip} ${citation.knowledge_domain === "POLICY" ? styles.policyCitation : styles.projectCitation} ${isSelectedCitation(selectedCitation, citation) ? styles.citationSelected : ""}`}
          aria-pressed={isSelectedCitation(selectedCitation, citation)}
          onClick={() => onSelect(citation)}
        >
          <MemberIcon name="document" size={13} />
          <span className={styles.citationText}>
            {citationLabel(citation, t("sourceFallback", { id: citation.chunk_id }))}
          </span>
        </button>
      ))}
    </div>
  );
}

function ClaimAnswer({
  claims,
  selectedCitation,
  onSelect,
}: {
  claims: ChatClaim[];
  selectedCitation: ChatCitation | null;
  onSelect: (citation: ChatCitation) => void;
}) {
  const t = useTranslations("chat");
  const orderedClaims = [...claims].sort((left, right) => left.claim_index - right.claim_index);
  return (
    <div className={styles.claimList}>
      {orderedClaims.map((claim) => (
        <section
          className={styles.claim}
          key={claim.claim_index}
          aria-label={t("claim", { count: claim.claim_index + 1 })}
        >
          <div className={styles.markdown}>
            <SafeMarkdown source={claim.text} />
          </div>
          <CitationReferences
            citations={claim.citations}
            selectedCitation={selectedCitation}
            onSelect={onSelect}
            claimIndex={claim.claim_index}
          />
        </section>
      ))}
    </div>
  );
}

function GuidanceAnswer({ guidance }: { guidance: ChatGuidance[] }) {
  const t = useTranslations("chat");
  return (
    <section className={styles.guidanceList} aria-label={t("generalGuidance")}>
      <div className={styles.guidanceHeader}>{t("generalGuidance")}</div>
      <p className={styles.guidanceDescription}>{t("generalGuidanceDescription")}</p>
      {guidance.map((item, index) => (
        <div className={styles.guidanceItem} key={`${item.kind}-${index}`}>
          <div className={styles.guidanceKind}>
            {item.kind === "instruction" ? t("guidanceInstruction") : t("guidanceExplanation")}
          </div>
          <div className={styles.markdown}>
            <SafeMarkdown source={item.text} />
          </div>
        </div>
      ))}
    </section>
  );
}

export function ChatScreen({
  embeddedUser,
  newConversationRequest = 0,
}: {
  embeddedUser?: CurrentUser;
  newConversationRequest?: number;
} = {}) {
  const t = useTranslations("chat");
  const memberT = useTranslations("member");
  const common = useTranslations("common");
  const router = useRouter();
  const searchParams = useSearchParams();
  const { theme, toggleTheme } = usePersistentTheme();
  const {
    user,
    loading: sessionLoading,
    error: sessionError,
    signOut,
    updatePreferences,
  } = useSession();
  const embeddingWarmupState = useEmbeddingWarmup(Boolean(user));
  const memberships = useProjectMemberships(Boolean(user));
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [scope, setScope] = useState<ChatScope>({ type: "POLICY" });
  const [draft, setDraft] = useState("");
  const [selectedCitation, setSelectedCitation] = useState<ChatCitation | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [pendingTurn, setPendingTurn] = useState<{ question: string; scope: ChatScope } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const initializedProjectScope = useRef(false);
  const requestControllerRef = useRef<AbortController | null>(null);
  const requestedProjectId = useMemo(() => {
    const value = searchParams.get("project");
    return value && /^\d+$/.test(value) ? Number(value) : null;
  }, [searchParams]);

  const authorizedMembershipIds = useMemo(
    () => new Set(memberships.data.map((membership) => membership.membershipId)),
    [memberships.data],
  );
  const effectiveScope: ChatScope =
    scope.type === "PROJECT" &&
    !memberships.isLoading &&
    !authorizedMembershipIds.has(scope.membershipId)
      ? { type: "POLICY" }
      : scope;
  const currentProject =
    effectiveScope.type === "PROJECT"
      ? memberships.data.find(
          (membership) => membership.membershipId === effectiveScope.membershipId,
        )
      : null;
  const returnProject =
    currentProject ??
    memberships.data.find((membership) => membership.projectId === requestedProjectId) ??
    null;
  // A member enters chat from one already-authorized project. Keep the chooser honest about
  // that active context; the server remains the authority for the membership itself.
  const scopeMemberships =
    user?.system_role === null && requestedProjectId !== null
      ? memberships.data.filter((membership) => membership.projectId === requestedProjectId)
      : memberships.data;
  const memberHref = returnProject ? `/user?project=${returnProject.projectId}` : "/select-project";
  const memberHrefSeparator = memberHref.includes("?") ? "&" : "?";
  const blockersHref = `${memberHref}${memberHrefSeparator}view=blockers`;
  const conventionsHref = `${memberHref}${memberHrefSeparator}view=conventions`;
  const chatHref = returnProject ? `/chat?project=${returnProject.projectId}` : "/chat";
  const showMemberNavigation = memberships.data.length > 0;

  // History belongs to the server; the browser only remembers which conversation it was in.
  // Re-keys on scope change, so a policy thread and a project thread never bleed into each other.
  const conversation = useConversation(effectiveScope);
  const turns = conversation.turns;
  const previousNewConversationRequest = useRef(newConversationRequest);

  useEffect(() => {
    if (previousNewConversationRequest.current === newConversationRequest) return;
    previousNewConversationRequest.current = newConversationRequest;
    conversation.reset();
    setSelectedCitation(null);
    setError(null);
    textareaRef.current?.focus();
  }, [conversation, newConversationRequest]);

  useEffect(() => {
    if (!sessionLoading && !user && sessionError?.status === 401)
      router.replace("/login?next=/chat");
  }, [router, sessionError, sessionLoading, user]);

  useEffect(() => {
    if (initializedProjectScope.current || memberships.isLoading) return;
    initializedProjectScope.current = true;
    const membership = memberships.data.find((item) => item.projectId === requestedProjectId);
    if (!membership) return;
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setScope({
        type: "PROJECT",
        membershipId: membership.membershipId,
        projectName: membership.projectName,
        projectKey: membership.projectKey,
      });
    });
    return () => {
      active = false;
    };
  }, [memberships.data, memberships.isLoading, requestedProjectId]);

  const changeScope = (next: ChatScope) => {
    if (isSending) return;
    setScope(next);
    setError(null);
    if (next.type === "PROJECT") {
      const membership = memberships.data.find((item) => item.membershipId === next.membershipId);
      if (membership) router.replace(`/chat?project=${membership.projectId}`, { scroll: false });
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: "end" });
  }, [isSending, turns.length]);

  // A compact composer starts as one line and grows only when the draft needs it.
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    const maxHeight = 128;
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [draft]);

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const question = draft.trim();
    if (!question || isSending || embeddingWarmupState === "preparing") return;
    const submittedScope = effectiveScope;
    const basePrompt: ChatPrompt =
      submittedScope.type === "POLICY"
        ? { mode: "policy", question }
        : { mode: "project", question, membershipId: submittedScope.membershipId };
    setDraft("");
    setError(null);
    setIsSending(true);
    setPendingTurn({ question, scope: submittedScope });
    const controller = new AbortController();
    requestControllerRef.current = controller;
    try {
      let response;
      try {
        response = await askChat(
          { ...basePrompt, conversationId: conversation.conversationId },
          controller.signal,
        );
      } catch (caught) {
        // 404: the conversation no longer exists. 409: its frozen scope no longer matches this
        // request. Both mean "this thread cannot continue", and both are recoverable by starting a
        // new one — so recover silently instead of surfacing an error the user cannot act on.
        if (
          caught instanceof ApiError &&
          (caught.status === 404 || caught.status === 409) &&
          conversation.conversationId
        ) {
          conversation.reset();
          response = await askChat(basePrompt, controller.signal);
        } else {
          throw caught;
        }
      }
      conversation.appendTurn(question, submittedScope, response);
    } catch (caught) {
      if (controller.signal.aborted) {
        setDraft(question);
        return;
      }
      if (caught instanceof ApiError && caught.status === 401) {
        router.replace("/login?next=/chat");
        return;
      }
      if (
        caught instanceof ApiError &&
        (caught.status === 403 || caught.status === 422) &&
        submittedScope.type === "PROJECT"
      ) {
        setScope({ type: "POLICY" });
        memberships.refetch();
        setError(t("projectAccessError"));
      } else {
        setError(caught instanceof Error ? caught.message : t("answerError"));
      }
      setDraft(question);
    } finally {
      if (requestControllerRef.current === controller) requestControllerRef.current = null;
      setPendingTurn(null);
      setIsSending(false);
      window.setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }

  function stopGeneration() {
    requestControllerRef.current?.abort();
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit();
    }
  }

  const effectiveUser = user ?? embeddedUser ?? null;
  const preferenceUser = user ?? embeddedUser ?? null;

  if (sessionLoading && !embeddedUser)
    return <main className={styles.sessionLoading} aria-label={t("loadingChat")} />;
  if (!effectiveUser) {
    if (sessionError?.status === 401) return null;
    return (
      <main className={styles.sessionError} role="alert">
        {t("sessionError")}
      </main>
    );
  }

  const roleLabel =
    effectiveUser.system_role === "ADMIN"
      ? t("roleAdmin")
      : effectiveUser.system_role === "HR"
        ? t("roleHr")
        : t("roleMember");
  const suggestions =
    effectiveScope.type === "POLICY"
      ? [t("suggestionPolicy1"), t("suggestionPolicy2"), t("suggestionPolicy3")]
      : [t("suggestionProject1"), t("suggestionProject2"), t("suggestionProject3")];

  return (
    <div
      className={`${embeddedUser ? styles.chatEmbedded : portalStyles.portal} ${styles.chatApp} ralion-workspace`}
      data-theme={theme}
    >
      {!embeddedUser && (
        <MemberSidebar
          member={effectiveUser}
          activeView="chat"
          checklistHref={memberHref}
          blockersHref={blockersHref}
          conventionsHref={conventionsHref}
          blockerCount={0}
          roleLabel={roleLabel}
          showMemberNavigation={showMemberNavigation}
          switchProjectHref={showMemberNavigation ? "/select-project" : undefined}
          policyHref="/documents"
          onSignOut={() => void signOut()}
        />
      )}
      {!embeddedUser && (
        <MobileNavDrawer
          label={memberT("navigation")}
          onClose={() => setMobileNavOpen(false)}
          open={mobileNavOpen}
        >
          <nav className={portalStyles.mobileDrawerNav}>
            {showMemberNavigation && (
              <Link href={memberHref} onClick={() => setMobileNavOpen(false)}>
                {memberT("checklist")}
              </Link>
            )}
            <Link href={chatHref} aria-current="page" onClick={() => setMobileNavOpen(false)}>
              {memberT("chat")}
            </Link>
            <Link href="/documents" onClick={() => setMobileNavOpen(false)}>
              {memberT("policy.title")}
            </Link>
            {showMemberNavigation && (
              <>
                <Link href={conventionsHref} onClick={() => setMobileNavOpen(false)}>
                  {memberT("conventions")}
                </Link>
                <Link href={blockersHref} onClick={() => setMobileNavOpen(false)}>
                  {memberT("blockers")}
                </Link>
                <Link href="/select-project" onClick={() => setMobileNavOpen(false)}>
                  {memberT("switchProject")}
                </Link>
              </>
            )}
          </nav>
          <div className={portalStyles.mobileDrawerFoot}>
            <LanguageSwitcher />
            <button
              type="button"
              onClick={() => {
                setMobileNavOpen(false);
                void signOut();
              }}
            >
              {common("logout")}
            </button>
          </div>
        </MobileNavDrawer>
      )}
      <main className={styles.workspace}>
        <header className={styles.chatHeader}>
          <button
            aria-label={common("openMenu")}
            className={portalStyles.mobileMenuButton}
            onClick={() => setMobileNavOpen(true)}
            type="button"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <BrandHomeLink className={styles.mobileBrand}>
            <RalionBrand />
          </BrandHomeLink>
          <div>
            <h1 className={portalStyles.pageTitleWithIcon}>
              <span>
                <MemberIcon name="chat" size={20} />
              </span>
              {t("title")}
            </h1>
          </div>
          <span className={styles.headerScope}>
            {effectiveScope.type === "POLICY" ? t("companyKnowledge") : effectiveScope.projectName}
          </span>
          <button
            type="button"
            className={styles.themeToggle}
            aria-label={memberT("theme")}
            title={memberT("theme")}
            onClick={toggleTheme}
          >
            <MemberIcon name={theme === "dark" ? "sun" : "moon"} size={16} />
          </button>
          {turns.length > 0 && (
            <button
              type="button"
              className={styles.newConversation}
              onClick={() => {
                conversation.reset();
                setSelectedCitation(null);
                setError(null);
                textareaRef.current?.focus();
              }}
            >
              {t("newConversation")}
            </button>
          )}
        </header>
        <div className={styles.chatLayout}>
          <section className={styles.conversationPane} aria-label={t("conversation")}>
            <div className={styles.conversationScroll}>
              <div className={styles.conversationColumn}>
                {turns.length === 0 ? (
                  <div className={styles.emptyState}>
                    <h2>{t("title")}</h2>
                    <div className={styles.suggestions}>
                      <span>{t("suggestedQuestions")}</span>
                      {suggestions.map((suggestion) => (
                        <button
                          type="button"
                          key={suggestion}
                          onClick={() => {
                            setDraft(suggestion);
                            textareaRef.current?.focus();
                          }}
                        >
                          {suggestion}
                          <MemberIcon name="arrow" size={15} />
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  turns.map((turn) => (
                    <div className={styles.turn} key={turn.id}>
                      <div className={styles.userMessage}>
                        <p>{turn.question}</p>
                      </div>
                      <AssistantMessage>
                        {turn.response.conflict && (
                          <div className={styles.conflictNotice} role="status">
                            <strong>{t("sourcesConflict")}</strong>
                            <p>{turn.response.conflict}</p>
                          </div>
                        )}
                        {!turn.response.fallback && turn.response.claims.length > 0 && (
                          <ClaimAnswer
                            claims={turn.response.claims}
                            selectedCitation={selectedCitation}
                            onSelect={setSelectedCitation}
                          />
                        )}
                        {!turn.response.fallback &&
                          (turn.response.general_guidance?.length ?? 0) > 0 && (
                            <GuidanceAnswer guidance={turn.response.general_guidance ?? []} />
                          )}
                        {turn.response.fallback ||
                        (turn.response.claims.length === 0 &&
                          (turn.response.general_guidance?.length ?? 0) === 0) ? (
                          <div className={styles.markdown}>
                            <SafeMarkdown source={turn.response.answer} />
                          </div>
                        ) : null}
                        {turn.response.fallback && turn.response.citations.length > 0 && (
                          <CitationReferences
                            citations={turn.response.citations}
                            selectedCitation={selectedCitation}
                            onSelect={setSelectedCitation}
                            ariaLabel={t("relatedMaterial")}
                          />
                        )}
                      </AssistantMessage>
                    </div>
                  ))
                )}
                {isSending && (
                  <div className={styles.turn} aria-live="polite">
                    <div className={styles.userMessage}>
                      <p>{pendingTurn?.question}</p>
                    </div>
                    <AssistantMessage>
                      <div className={styles.thinking} role="status">
                        <span className={styles.thinkingDots} aria-hidden="true">
                          <i />
                          <i />
                          <i />
                        </span>
                        <span>{t("checking")}</span>
                      </div>
                    </AssistantMessage>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>
            <div className={styles.composerDock}>
              {embeddingWarmupState === "preparing" && (
                <p className={styles.assistantPreparing} role="status" aria-live="polite">
                  <span className={styles.preparingDot} aria-hidden="true" />
                  {t("preparingAssistant")}
                </p>
              )}
              <form className={styles.composer} onSubmit={submit}>
                <textarea
                  ref={textareaRef}
                  value={draft}
                  maxLength={8000}
                  rows={1}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder={t("placeholder")}
                  aria-label={t("questionLabel")}
                />
                <div className={styles.composerFooter}>
                  <ScopeSelector
                    scope={effectiveScope}
                    memberships={scopeMemberships}
                    loading={memberships.isLoading}
                    onChange={changeScope}
                  />
                  {preferenceUser && (
                    <AccountChatPreferences
                      compact
                      binding={{
                        responseLength: preferenceUser.response_length,
                        responseTone: preferenceUser.response_tone,
                        onUpdate: updatePreferences,
                      }}
                    />
                  )}
                  <span className={styles.keyboardHint}>{t("keyboardHint")}</span>
                  {isSending ? (
                    <button
                      type="button"
                      className={styles.stopButton}
                      onClick={stopGeneration}
                      aria-label={t("checking")}
                    >
                      <span className={styles.sendSpinner} aria-hidden="true" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      className={styles.sendButton}
                      disabled={!draft.trim() || embeddingWarmupState === "preparing"}
                      aria-label={t("send")}
                    >
                      <MemberIcon name="arrow" size={17} />
                    </button>
                  )}
                </div>
              </form>
              {(error || memberships.error) && (
                <p className={styles.composerError} role="alert">
                  {error || memberships.error?.message}
                </p>
              )}
            </div>
          </section>
        </div>
        {selectedCitation && (
          <DocumentPreviewModal
            title={citationLabel(
              selectedCitation,
              t("sourceFallback", { id: selectedCitation.chunk_id }),
            )}
            sourceUrl={selectedCitation.source_url ?? ""}
            highlightSection={selectedCitation.section_heading ?? null}
            highlightSnippet={selectedCitation.source_content ?? selectedCitation.quote ?? null}
            onClose={() => setSelectedCitation(null)}
          />
        )}
      </main>
    </div>
  );
}
