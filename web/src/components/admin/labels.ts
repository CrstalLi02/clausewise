/** Display mappings for Loop phases and states. */

export const PHASE_LABEL: Record<string, string> = {
  human_in_loop: "Human in the loop",
  human_on_loop: "Human on the loop",
  human_out_of_loop: "Human out of the loop",
};

export const PHASE_DESC: Record<string, string> = {
  human_in_loop: "All automatic outputs take effect only after human review; humans make 100% of decisions",
  human_on_loop: "High-confidence outputs apply automatically and low-confidence ones go to the review queue; humans are reviewers",
  human_out_of_loop: "Fully automatic within the defined scope; humans only set boundaries and goals and act as supervisors",
};

export function phaseLabel(phase?: string): string {
  return PHASE_LABEL[phase || ""] || phase || "Unknown";
}

export function phaseBadgeClass(phase?: string): string {
  if (phase === "human_out_of_loop") return "badgeGreen";
  if (phase === "human_on_loop") return "badgeAmber";
  return "badgeBlue";
}

export const LOOP_STAGES = [
  { key: "execute", name: "Execute", desc: "Answer with the current Skills/Hooks/Rules and record traces" },
  { key: "observe", name: "Observe", desc: "Collect explicit/implicit/automatic feedback signals" },
  { key: "reflect", name: "Reflect", desc: "Analyze bad case root causes (retrieval/intent/generation/gap)" },
  { key: "adapt", name: "Adapt", desc: "Generate Skill/Hook/Rule updates for review" },
  { key: "deploy", name: "Deploy", desc: "Canary release, full rollout after backtesting, back to Execute" },
];
