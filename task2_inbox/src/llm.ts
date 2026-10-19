import Anthropic from "@anthropic-ai/sdk";

// USD per 1M tokens [input, output]. PLACEHOLDERS - verify at anthropic.com/pricing before quoting numbers.
export const PRICES: Record<string, [number, number]> = {
  "claude-haiku-5-5": [1, 5], "claude-sonnet-5-5": [3, 15], "claude-opus-5-5": [5, 25],
};
export const MODELS = {
  triage: process.env["MODEL_TRIAGE"] ?? "claude-haiku-5-5",
  draft: process.env["MODEL_DRAFT"] ?? "claude-sonnet-5-5",
  learn: process.env["MODEL_LEARN"] ?? "claude-sonnet-5-5",
};
export interface LedgerRow { label: string; model: string; ms: number; usd: number }
export const LEDGER: LedgerRow[] = [];
let client: Anthropic | undefined;

export function costUsd(model: string, tin: number, tout: number): number {
  const [pi, po] = PRICES[model] ?? [3, 15];
  return (tin * pi + tout * po) / 1_000_000;
}

/** Forced tool call = the reply always matches the JSON schema. */
export async function callJson<T>(opts: {
  model: string; system: string; user: string; schema: Record<string, unknown>; label: string; maxTokens?: number;
}): Promise<{ data: T; usd: number }> {
  client ??= new Anthropic({ maxRetries: 4, timeout: 90_000 });
  const t0 = Date.now();
  const r = await client.messages.create({
    model: opts.model, max_tokens: opts.maxTokens ?? 1500, system: opts.system,
    messages: [{ role: "user", content: opts.user }],
    tools: [{ name: "respond", description: "Return the result.", input_schema: opts.schema as Anthropic.Tool.InputSchema }],
    tool_choice: { type: "tool", name: "respond" },
  });
  const usd = costUsd(opts.model, r.usage.input_tokens, r.usage.output_tokens);
  LEDGER.push({ label: opts.label, model: opts.model, ms: Date.now() - t0, usd });
  const block = r.content.find((b) => b.type === "tool_use");
  if (!block || block.type !== "tool_use") throw new Error("model returned no tool call");
  return { data: block.input as T, usd };
}
