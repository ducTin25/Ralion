import { authHeaders } from "@/features/auth/session";
import { CHAT_CONVERSATIONS_ENDPOINT, CHAT_ENDPOINT, requestJson } from "@/lib/api";
import type { ChatPrompt, ChatResponse, StoredConversation } from "@/types/chat";

// Chat first embeds the question through the remote BGE-M3 service before it
// can retrieve evidence and generate an answer.  Its request budget must be
// longer than the short default used by ordinary CRUD API calls.
// Bootstrap safety ceiling plus a small network margin; this is not the product latency SLO.
const CHAT_REQUEST_TIMEOUT_MS = 30_000;

type ChatApiRequest = {
  question: string;
  mode: "PROJECT" | "POLICY";
  membership_id?: number;
  conversation_id?: string;
};

function toChatApiRequest(prompt: ChatPrompt): ChatApiRequest {
  // Omitting conversation_id is how the client asks for a new conversation.
  const conversation = prompt.conversationId ? { conversation_id: prompt.conversationId } : {};
  if (prompt.mode === "project") {
    return {
      question: prompt.question,
      mode: "PROJECT",
      membership_id: prompt.membershipId,
      ...conversation,
    };
  }
  return { question: prompt.question, mode: "POLICY", ...conversation };
}

export function askChat(prompt: ChatPrompt, signal?: AbortSignal): Promise<ChatResponse> {
  return requestJson<ChatResponse>(
    CHAT_ENDPOINT,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(toChatApiRequest(prompt)),
      signal,
    },
    { timeoutMs: CHAT_REQUEST_TIMEOUT_MS },
  );
}

/** Rebuild a thread after a reload. The history lives on the server, not in browser storage. */
export function fetchConversation(conversationId: string): Promise<StoredConversation> {
  return requestJson<StoredConversation>(
    `${CHAT_CONVERSATIONS_ENDPOINT}/${encodeURIComponent(conversationId)}`,
    { method: "GET", headers: authHeaders() },
  );
}
