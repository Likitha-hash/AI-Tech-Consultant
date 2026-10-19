export const CATEGORIES = [
  "how_to", "new_project", "refund", "cancellation", "complaint", "quote",
  "follow_up", "billing", "bug_report", "account_access", "feature_request", "other",
] as const;
export type Category = (typeof CATEGORIES)[number];

export interface Email { id: string; name: string; from: string; subject: string; body: string; receivedAt: string }

export interface Triage {
  category: Category;
  risk: "low" | "high";            // high = money, legal threat, angry customer, anything irreversible
  urgency: "low" | "normal" | "urgent";
  key_question: string;            // what to ask the Knowledge Brain
  sentiment: "positive" | "neutral" | "negative";
}

export interface Draft { subject: string; body: string; confidence: number; needs_human_reason: string }

export interface BrainResult { confident: boolean; answer: string; sources: string[]; taskId: number | null }

export type Status = "pending" | "sent_as_is" | "edited" | "own_reply" | "auto_sent";

export interface DraftRecord {
  emailId: string; triage: Triage; draft: Draft; brain: BrainResult;
  promptVersion: string; createdAt: string; status: Status;
  finalBody?: string; similarity?: number; audit: boolean; auditResult?: "ok" | "bad";
  costUsd: number;
}

export interface Lesson { id: string; scope: Category | "global"; rule: string; evidence: string; createdAt: string; active: boolean }
export interface Autopilot { streak: number; enabled: boolean; reason: string }

export interface State {
  emails: Email[];
  records: Record<string, DraftRecord>;
  lessons: Lesson[];
  autopilot: Partial<Record<Category, Autopilot>>;
  examples: Partial<Record<Category, string[]>>;   // human-approved replies, used as few-shot
  outbox: { emailId: string; body: string; auto: boolean; at: string }[];
  autoCount: number;
}
