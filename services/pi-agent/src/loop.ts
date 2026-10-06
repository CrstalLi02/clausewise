/**
 * Loop Engine (built on the pi agent loop): Observe → Reflect → Adapt.
 * The Loop agent reads pending feedback, attributes root causes, and calls tools to persist Skills / Hooks / Rules.
 */
import type { AgentTool } from "@earendil-works/pi-agent-core";
import type { Config } from "./config.js";
import { runAgentJson, type AgentRuntime } from "./agents.js";

const LOOP_PROMPT = `You are the Loop evolution agent of the "Clausewise" system (a feedback-driven self-optimization loop).

Follow these steps:
1. Call the list_pending_feedback tool to read pending feedback.
2. Analyze bad cases (feedback whose signal is down/correction/verifier_fail) and attribute them to: retrieval, intent, generation, or knowledge_gap.
3. For frequent reusable patterns, persist them through tools:
   - save_skill: a kind of question recurs and has a stable solution → persist as a Skill
   - save_hook: extra actions triggered under specific conditions → persist as a Hook
   - save_rule: a hard constraint that must be obeyed → persist as a Rule
4. Finally output a JSON summary:{"observed":0,"bad_cases":0,"root_causes":{},"adaptations":[{"type":"skill|hook|rule","name":"..."}]}`;

function pickTools(tools: AgentTool[], names: string[]): AgentTool[] {
  return tools.filter((t) => names.includes(t.name));
}

export async function runLoop(
  runtime: AgentRuntime,
  config: Config,
): Promise<unknown> {
  if (!config.loopEnabled) {
    return { skipped: true, reason: "loop disabled" };
  }
  const tools = pickTools(runtime.tools, [
    "list_pending_feedback",
    "save_skill",
    "save_hook",
    "save_rule",
  ]);
  try {
    return await runAgentJson(runtime, LOOP_PROMPT, "Run one Loop evolution cycle.", tools);
  } catch (err) {
    console.warn("Loop execution failed:", err);
    return { observed: 0, bad_cases: 0, root_causes: {}, adaptations: [], error: String(err) };
  }
}
