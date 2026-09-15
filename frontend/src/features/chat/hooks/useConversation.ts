"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchConversation } from "@/features/chat/api";
import { ApiError } from "@/lib/api";
import type { ChatResponse, ChatScope, ConversationTurn, StoredConversation } from "@/types/chat";

/**
 * Conversation pointer + rehydration.
 *
 * Only the conversation *id* lives in the browser; the history itself lives on the server, which
 * is what makes it survive a reload or a new authenticated session on the same device. Only an
 * opaque server-owned id is persisted; the server still rechecks ownership before returning a
 * transcript. "New conversation" is the explicit action that clears this pointer.
 *
 * The pointer is keyed per scope, so switching between Company Policy and a project can never
 * continue the wrong conversation.
 */
function storageKey(scope: ChatScope): string {
  return scope.type === "POLICY"
    ? "ralion.chat.conversation.POLICY"
    : `ralion.chat.conversation.PROJECT.${scope.membershipId}`;
}

function readPointer(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key) ?? window.sessionStorage.getItem(key);
  } catch {
    return null; // Private mode or a blocked storage partition: degrade to no memory pointer.
  }
}

function writePointer(key: string, value: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
      // Remove the previous storage location too, so an explicit reset cannot be revived by a
      // legacy pointer after an upgrade.
      window.sessionStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
      window.sessionStorage.removeItem(key);
    }
  } catch {
    // Ignore: losing the pointer costs continuity, never correctness.
  }
}

function matchesScope(
  stored: StoredConversation,
  scopeType: ChatScope["type"],
  membershipId: number | null,
): boolean {
  if (stored.mode !== scopeType) return false;
  return scopeType === "POLICY"
    ? stored.membership_id === null
    : stored.membership_id === membershipId;
}

function toTurns(stored: StoredConversation, scope: ChatScope): ConversationTurn[] {
  return stored.turns
    .filter((turn) => turn.answer !== null)
    .map((turn) => ({
      id: `stored-${stored.conversation_id}-${turn.turn_index}`,
      question: turn.question,
      scope,
      response: {
        answer: turn.answer ?? "",
        citations: turn.citations,
        fallback: turn.fallback,
        fallback_reason: turn.fallback_reason,
        trace_id: turn.trace_id ?? "",
        answer_status: turn.answer_status ?? (turn.fallback ? "fallback" : "verified"),
        validator_outcome: turn.validator_outcome,
        claims: turn.claims,
        conflict: turn.conflict,
        general_guidance: turn.general_guidance ?? [],
        answer_shape:
          turn.answer_shape ??
          (turn.general_guidance?.length
            ? turn.claims.length
              ? "mixed"
              : "guidance_only"
            : "internal_only"),
        conversation_id: stored.conversation_id,
      },
    }));
}

export function useConversation(scope: ChatScope) {
  const key = useMemo(() => storageKey(scope), [scope]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [hydrating, setHydrating] = useState(false);
  const scopeType = scope.type;
  const membershipId = scope.type === "PROJECT" ? scope.membershipId : null;
  const projectName = scope.type === "PROJECT" ? scope.projectName : null;
  const projectKey = scope.type === "PROJECT" ? scope.projectKey : null;

  useEffect(() => {
    const pointer = readPointer(key);
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setConversationId(pointer);
      setTurns([]);
      setHydrating(Boolean(pointer));
    });
    if (!pointer) return () => void (active = false);

    const rehydrationScope: ChatScope =
      scopeType === "POLICY"
        ? { type: "POLICY" }
        : {
            type: "PROJECT",
            membershipId: membershipId!,
            projectName: projectName!,
            projectKey: projectKey!,
          };
    fetchConversation(pointer)
      .then((stored) => {
        if (!active) return;
        if (!matchesScope(stored, scopeType, membershipId)) {
          writePointer(key, null);
          setConversationId(null);
          return;
        }
        setTurns(toTurns(stored, rehydrationScope));
      })
      .catch((error) => {
        if (!active) return;
        // 404 means the pointer is stale (or was tampered with): forget it and start fresh
        // rather than showing an error the user cannot act on.
        if (error instanceof ApiError && error.status === 404) {
          writePointer(key, null);
          setConversationId(null);
        }
      })
      .finally(() => {
        if (active) setHydrating(false);
      });

    return () => {
      active = false;
    };
  }, [key, membershipId, projectKey, projectName, scopeType]);

  const appendTurn = useCallback(
    (question: string, turnScope: ChatScope, response: ChatResponse) => {
      writePointer(storageKey(turnScope), response.conversation_id);
      setConversationId(response.conversation_id);
      setTurns((current) => [
        ...current,
        {
          id: `${response.conversation_id}-${current.length}`,
          question,
          scope: turnScope,
          response,
        },
      ]);
    },
    [],
  );

  const reset = useCallback(() => {
    writePointer(key, null);
    setConversationId(null);
    setTurns([]);
  }, [key]);

  return { conversationId, turns, hydrating, appendTurn, reset };
}
