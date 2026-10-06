/**
 * Runtime wiring: model + streamFn + tools, shared by all agents.
 */
import type { Config } from "./config.js";
import { buildModels, getMainModel } from "./providers.js";
import { buildTools } from "./tools.js";
import type { AgentRuntime } from "./agents.js";

export interface Runtime {
  runtime: AgentRuntime;
  tools: AgentRuntime["tools"];
}

export function buildRuntime(config: Config): Runtime {
  const models = buildModels(config);
  const model = getMainModel(models, config);
  const tools = buildTools(config);
  return {
    runtime: {
      model,
      streamFn: models.streamSimple.bind(models),
      tools,
    },
    tools,
  };
}
