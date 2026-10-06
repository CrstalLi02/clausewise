/**
 * Orchestrator: orchestrates the multi-agent DAG (built on the pi agent loop).
 *
 * Intent → Rewrite → Retrieve (Python hybrid retrieval) → Answer (pi Agent + tools) → Verify (≤2 rewrites)
 */
import type { AgentTool } from "@earendil-works/pi-agent-core";
import type { Config } from "./config.js";
import {
  ANSWER_PROMPT,
  INTENT_PROMPT,
  REWRITER_PROMPT,
  VERIFIER_PROMPT,
  runAgent,
  runAgentJson,
  type AgentRuntime,
} from "./agents.js";
import { retrieveChunks, type Chunk } from "./backend.js";

export interface AnswerInput {
  query: string;
  sessionId?: string;
  userId?: string;
  deptIds?: string[] | null;
}

export interface Citation {
  doc_id: string;
  doc_title: string;
  dept_id: string;
  chunk_index: number;
  section_path: string[];
  snippet: string;
}

export interface AnswerResult {
  sessionId: string;
  answer: string;
  citations: Citation[];
  deptIds: string[];
  intentType: string;
  confidence: number;
  verification: { passed: boolean; score: number; issues: string[] };
}

const MAX_VERIFY_RETRY = 2;

function pickTools(tools: AgentTool[], names: string[]): AgentTool[] {
  return tools.filter((t) => names.includes(t.name));
}

function toCitations(chunks: Chunk[]): Citation[] {
  return chunks.map((c) => ({
    doc_id: c.doc_id ?? "",
    doc_title: c.doc_title ?? c.section_title ?? "",
    dept_id: c.dept_id ?? "",
    chunk_index: c.chunk_index ?? 0,
    section_path: c.section_path ?? [],
    snippet: (c.content ?? "").slice(0, 200),
  }));
}

function formatChunks(chunks: Chunk[]): string {
  return chunks
    .map((c, i) => `[Source ${i + 1}] ${c.content ?? ""}`)
    .join("\n\n");
}

export async function answer(
  runtime: AgentRuntime,
  config: Config,
  input: AnswerInput,
): Promise<AnswerResult> {
  const sessionId = input.sessionId ?? crypto.randomUUID();
  const allTools = runtime.tools;

  // 1. Intent
  let intentType = "other";
  let deptIds: string[] = [];
  let needsCrossDept = false;
  try {
    const intent = (await runAgentJson(
      runtime,
      INTENT_PROMPT,
      `User question: ${input.query}`,
      pickTools(allTools, ["list_departments"]),
    )) as { type?: string; depts?: string[]; needs_cross_dept?: boolean; confidence?: number };
    intentType = intent.type ?? "other";
    deptIds = (intent.depts ?? []).filter((d) => d && d !== "dept_all");
    needsCrossDept = Boolean(intent.needs_cross_dept);
  } catch (err) {
    console.warn("Intent failed, using defaults:", err);
  }

  // 2. Rewrite
  let queries: string[] = [input.query];
  try {
    const rewriter = (await runAgentJson(
      runtime,
      REWRITER_PROMPT,
      `User question: ${input.query}\nIntent: ${intentType}`,
      pickTools(allTools, ["get_glossary"]),
    )) as { queries?: string[] };
    if (Array.isArray(rewriter.queries) && rewriter.queries.length > 0) {
      queries = rewriter.queries.filter(Boolean);
    }
  } catch (err) {
    console.warn("Rewrite failed, using the original query:", err);
  }

  // 3. Retrieve (Python hybrid retrieval; multiple queries merged and deduplicated)
  const resolvedDepts = input.deptIds && input.deptIds.length > 0 ? input.deptIds : deptIds;
  const seen = new Map<string, Chunk>();
  for (const q of queries) {
    const chunks = await retrieveChunks(config, q, resolvedDepts.length ? resolvedDepts : null, 5);
    for (const c of chunks) {
      if (c._id && !seen.has(c._id)) seen.set(c._id, c);
    }
  }
  const chunks = [...seen.values()].slice(0, 8);

  // 4. Answer (pi Agent + tools; can do extra retrieval / check the calendar)
  let answerText = await runAgent(
    runtime,
    ANSWER_PROMPT.replace("{chunks}", formatChunks(chunks) || "(no reference clauses)"),
    input.query,
    pickTools(allTools, ["lookup_calendar", "retrieve_documents"]),
  );

  // 5. Verify (up to 2 rewrites)
  let verification: { passed: boolean; score: number; issues: string[] } = {
    passed: true,
    score: 1,
    issues: [],
  };
  for (let i = 0; i < MAX_VERIFY_RETRY; i++) {
    try {
      const verdict = (await runAgentJson(
        runtime,
        VERIFIER_PROMPT,
        `User question: ${input.query}\nReference clauses: ${formatChunks(chunks)}\nAnswer: ${answerText}`,
      )) as { passed?: boolean; score?: number; issues?: string[] };
      verification = {
        passed: verdict.passed ?? true,
        score: verdict.score ?? 1,
        issues: verdict.issues ?? [],
      };
    } catch (err) {
      console.warn("Verify failed:", err);
      break;
    }
    if (verification.passed) break;
    answerText = await runAgent(
      runtime,
      ANSWER_PROMPT.replace("{chunks}", formatChunks(chunks)) +
        `\n\nThe previous answer had the following issues; please fix them: ${verification.issues.join("; ")}`,
      input.query,
      pickTools(allTools, ["lookup_calendar", "retrieve_documents"]),
    );
  }

  return {
    sessionId,
    answer: answerText,
    citations: toCitations(chunks),
    deptIds: resolvedDepts,
    intentType,
    confidence: needsCrossDept ? 0.75 : 0.8,
    verification,
  };
}
