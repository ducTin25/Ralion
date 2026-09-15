/** Presentation-only selection. The API adapter maps this to the backend contract. */
export type ChatMode = "project" | "policy";

export type ChatPrompt =
  | { mode: "project"; question: string; membershipId: number; conversationId?: string | null }
  | { mode: "policy"; question: string; conversationId?: string | null };

export type ChatCitation = {
  chunk_id: number;
  quote: string;
  knowledge_domain: "PROJECT" | "POLICY" | "";
  relevance_score: number;
  redacted: boolean;
  document_id?: number | null;
  version_id?: number | null;
  source_title?: string | null;
  source_url?: string | null;
  section_heading?: string | null;
  anchor?: string | null;
  source_content?: string | null;
};

export type ChatClaim = {
  claim_index: number;
  text: string;
  support_type: "direct" | "inferred";
  verdict: string;
  redacted: boolean;
  citations: ChatCitation[];
};

export type ChatGuidance = {
  text: string;
  kind: "instruction" | "explanation";
};

export type ChatAnswerStatus =
  "verified" | "partially_verified" | "conflict" | "fallback" | "general_guidance";
export type ChatValidatorOutcome = "passed" | "degraded" | "failed" | null;
export type ChatAnswerShape = "internal_only" | "mixed" | "guidance_only";

export type ChatResponse = {
  answer: string;
  citations: ChatCitation[];
  fallback: boolean;
  fallback_reason: string | null;
  trace_id: string;
  answer_status: ChatAnswerStatus;
  validator_outcome: ChatValidatorOutcome;
  claims: ChatClaim[];
  conflict: string | null;
  /** Optional for backwards compatibility with responses from before BGK was exposed. */
  general_guidance?: ChatGuidance[];
  answer_shape?: ChatAnswerShape;
  /** Always present, including on fallback turns, so the next question can continue this thread. */
  conversation_id: string;
};

export type ChatScope =
  | { type: "POLICY" }
  | { type: "PROJECT"; membershipId: number; projectName: string; projectKey: string };

export type ConversationTurn = {
  id: string;
  question: string;
  scope: ChatScope;
  response: ChatResponse;
};

/** Server-side transcript, used to rebuild the thread after a reload. */
export type StoredConversationTurn = {
  turn_index: number;
  question: string;
  answer: string | null;
  fallback: boolean;
  fallback_reason: string | null;
  trace_id: string | null;
  citations: ChatCitation[];
  answer_status: ChatAnswerStatus | null;
  validator_outcome: ChatValidatorOutcome;
  claims: ChatClaim[];
  conflict: string | null;
  general_guidance?: ChatGuidance[];
  answer_shape?: ChatAnswerShape;
};

export type StoredConversation = {
  conversation_id: string;
  mode: "PROJECT" | "POLICY";
  membership_id: number | null;
  turns: StoredConversationTurn[];
};
