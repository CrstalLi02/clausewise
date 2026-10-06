/**
 * Multi-agent definitions (built on pi Agent + tool calling).
 * Each agent is a pi Agent instance: systemPrompt + tools + agent loop (the model decides on its own which tools to call).
 */
import { Agent, type AgentTool } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai";
import { buildTools } from "./tools.js";
import type { Config } from "./config.js";

export interface AgentRuntime {
  model: Model<"openai-completions">;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  streamFn: any; // models.streamSimple.bind(models), third-party type boundary
  tools: AgentTool[];
}

export type AgentType = "intent" | "rewrite" | "answer" | "verify" | "reflect";

export interface AgentExecutionResult {
  agentType: AgentType;
  output: string | unknown;
  outputMode: "text" | "json";
  latencyMs: number;
}

/** Run a pi Agent and collect the final text output (accumulating streamed text_delta). */
export async function runAgent(
  runtime: AgentRuntime,
  systemPrompt: string,
  prompt: string,
  tools: AgentTool[] = [],
): Promise<string> {
  const agent = new Agent({
    initialState: {
      systemPrompt,
      model: runtime.model,
      tools,
    },
    streamFn: runtime.streamFn,
  });

  let text = "";
  const unsubscribe = agent.subscribe((event) => {
    if (
      event.type === "message_update" &&
      event.assistantMessageEvent.type === "text_delta"
    ) {
      text += event.assistantMessageEvent.delta;
    }
  });

  await agent.prompt(prompt);
  unsubscribe();
  const result = text.trim();
  if (!result && agent.state.errorMessage) {
    throw new Error(`agent error: ${agent.state.errorMessage}`);
  }
  return result;
}

/** Run and parse JSON output (tolerating code fences). */
export async function runAgentJson(
  runtime: AgentRuntime,
  systemPrompt: string,
  prompt: string,
  tools: AgentTool[] = [],
): Promise<unknown> {
  const raw = await runAgent(runtime, systemPrompt, prompt, tools);
  return extractJson(raw);
}

/**
 * Unified probabilistic agent execution entry point. The Python control plane passes in a prompt and allowedTools
 * that have passed permission, memory, and fact governance; pi only handles the agent loop / tool calling / model execution.
 */
export async function executeAgent(
  runtime: AgentRuntime,
  agentType: AgentType,
  systemPrompt: string,
  prompt: string,
  outputMode: "text" | "json",
  allowedTools: string[] = [],
): Promise<AgentExecutionResult> {
  const started = Date.now();
  const tools = runtime.tools.filter((tool) => allowedTools.includes(tool.name));
  const output = outputMode === "json"
    ? await runAgentJson(runtime, systemPrompt, prompt, tools)
    : await runAgent(runtime, systemPrompt, prompt, tools);
  return { agentType, output, outputMode, latencyMs: Date.now() - started };
}

export function extractJson(text: string): unknown {
  let s = text.trim();
  if (s.startsWith("```")) {
    s = s.replace(/^```[a-zA-Z]*\s*/, "").replace(/```\s*$/, "");
  }
  const start = Math.min(
    ...[s.indexOf("{"), s.indexOf("[")].filter((i) => i >= 0),
  );
  const end = Math.max(s.lastIndexOf("}"), s.lastIndexOf("]"));
  if (start < 0 || end < 0 || end <= start) {
    throw new Error(`Could not parse JSON: ${s.slice(0, 200)}`);
  }
  return JSON.parse(s.slice(start, end + 1));
}

// ---------------------------------------------------------------------------
// systemPrompt for each agent
// ---------------------------------------------------------------------------

export const INTENT_PROMPT = `You are the intent recognition agent of the "Clausewise" policy Q&A system.
First call the list_departments tool to get the valid department ids, then determine the intent type of the user question, the departments involved, the user's role, and whether cross-department collaboration is needed.
Finally output JSON only (no extra explanation):
{"type":"regulation_consult|process_guide|deadline_query|complaint|chitchat|other","depts":["dept_id"],"user_role":"student|teacher|admin","entities":{},"needs_cross_dept":false,"confidence":0.0}`;

export const REWRITER_PROMPT = `You are the query rewriting agent. Rewrite the user question into 1-3 queries better suited for retrieval (fill in omissions, normalize terminology).
You may call the get_glossary tool to get the glossary. Finally output JSON only:
{"queries":["query1","query2"]}`;

export const ANSWER_PROMPT = `You are "Clausewise", a school policy consultation assistant. Answer the user question based on the given policy clauses.
[Rules you must follow]
- Every answer must include citations of the source clauses (marked as [Source N]).
- Answer only based on the clauses and never fabricate; when the clauses contain no explicit answer you must say "No explicit provision was found in the current policy documents".
- For questions about deadlines/dates, you may call the lookup_calendar tool to check the school calendar.
- If the given clauses are insufficient, you may call the retrieve_documents tool for additional retrieval.

[Reference clauses]
{chunks}

Answer in concise, accurate English.`;

export const VERIFIER_PROMPT = `You are the answer verification agent. Check whether the answer is reliable and output JSON only:
{"passed":true/false,"score":0.0-1.0,"issues":["issue"]}
Checks: (1) whether key conclusions are supported by clauses (2) whether it contradicts the source text (3) whether key information is missing (4) whether the citation format is correct.`;
