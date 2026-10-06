/**
 * Agent toolset: pi agents access the Python backend's data and retrieval capabilities through tool calls (function calling).
 */
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "typebox";
import type { Config } from "./config.js";
import {
  getCalendar,
  getGlossary,
  listDepartments,
  listPendingFeedback,
  retrieveChunks,
  saveArtifact,
  submitFeedback,
} from "./backend.js";

function textResult(text: string, details: Record<string, unknown> = {}) {
  return { content: [{ type: "text" as const, text }], details };
}

interface RetrieveParams {
  query: string;
  dept_ids?: string[];
  top_k?: number;
}
interface FeedbackParams {
  query: string;
  answer: string;
  signal: string;
}

export function buildTools(config: Config): AgentTool[] {
  return [
    {
      name: "retrieve_documents",
      label: "Retrieve policy documents",
      description: "Hybrid retrieval (BM25 + vectors + reranking) over policy clause chunks, returning source passages relevant to the question.",
      parameters: Type.Object({
        query: Type.String({ description: "Retrieval query" }),
        dept_ids: Type.Optional(Type.Array(Type.String())),
        top_k: Type.Optional(Type.Number({ default: 5 })),
      }),
      execute: async (_id, rawParams) => {
        const params = rawParams as RetrieveParams;
        const chunks = await retrieveChunks(config, params.query, params.dept_ids ?? null, params.top_k ?? 5);
        const text = chunks.map((c, i) => `[Source ${i + 1}] ${c.content ?? ""}`).join("\n\n");
        return textResult(text || "No relevant clauses found", { count: chunks.length });
      },
    },
    {
      name: "lookup_calendar",
      label: "Look up school calendar",
      description: "Look up the current semester calendar (milestones such as semester start, holidays, and course registration weeks).",
      parameters: Type.Object({}),
      execute: async () => {
        const data = await getCalendar(config);
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
    {
      name: "list_departments",
      label: "List departments",
      description: "List all departments and their ids (used to determine which departments a question involves).",
      parameters: Type.Object({}),
      execute: async () => {
        const depts = await listDepartments(config);
        return textResult(depts.map((d) => `${d._id}(${d.name ?? ""})`).join(", "), { count: depts.length });
      },
    },
    {
      name: "get_glossary",
      label: "Look up glossary",
      description: "Look up the synonym/terminology mapping table, used for query rewriting and normalization.",
      parameters: Type.Object({}),
      execute: async () => {
        const data = await getGlossary(config);
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
    {
      name: "submit_feedback",
      label: "Submit feedback",
      description: "Write user feedback (thumbs-up/thumbs-down/correction) to the feedback queue for the Loop to consume.",
      parameters: Type.Object({
        query: Type.String(),
        answer: Type.String(),
        signal: Type.String({ description: "up | down | correction" }),
      }),
      execute: async (_id, rawParams) => {
        await submitFeedback(config, rawParams as FeedbackParams);
        return textResult("Feedback submitted", {});
      },
    },
    {
      name: "list_pending_feedback",
      label: "Read pending feedback",
      description: "Read feedback signals not yet consumed by the Loop.",
      parameters: Type.Object({}),
      execute: async () => {
        const data = await listPendingFeedback(config);
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
    {
      name: "save_skill",
      label: "Save Skill",
      description: "Write an automatically mined Skill draft to storage (pending review or auto-applied).",
      parameters: Type.Object({
        name: Type.String(),
        trigger: Type.String({ description: "Trigger condition description" }),
        steps: Type.String({ description: "Execution steps description" }),
        confidence: Type.Optional(Type.Number()),
      }),
      execute: async (_id, rawParams) => {
        const data = await saveArtifact(config, { type: "skill", ...(rawParams as Record<string, unknown>) });
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
    {
      name: "save_hook",
      label: "Save Hook",
      description: "Write an automatically mined Hook draft to storage.",
      parameters: Type.Object({
        name: Type.String(),
        trigger: Type.String({ description: "Trigger condition description" }),
        action: Type.String({ description: "Trigger action description" }),
        confidence: Type.Optional(Type.Number()),
      }),
      execute: async (_id, rawParams) => {
        const data = await saveArtifact(config, { type: "hook", ...(rawParams as Record<string, unknown>) });
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
    {
      name: "save_rule",
      label: "Save Rule",
      description: "Write an automatically derived Rule to storage.",
      parameters: Type.Object({
        name: Type.String(),
        content: Type.String({ description: "Rule content" }),
        confidence: Type.Optional(Type.Number()),
      }),
      execute: async (_id, rawParams) => {
        const data = await saveArtifact(config, { type: "rule", ...(rawParams as Record<string, unknown>) });
        return textResult(JSON.stringify(data, null, 2), {});
      },
    },
  ];
}
