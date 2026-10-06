/**
 * Model provider wiring: the unified LLM API from @earendil-works/pi-ai.
 *
 * - deepseek: primary chat model (OpenAI-compatible, https://api.deepseek.com)
 * - relay   : relay service (OpenAI-compatible, https://yunwu.ai/v1), for non-DeepSeek models
 */
import {
  createModels,
  createProvider,
  envApiKeyAuth,
  type Model,
  type Models,
} from "@earendil-works/pi-ai";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";
import type { Config } from "./config.js";

/** Build an OpenAI-completions-compatible model descriptor. */
function openAIModel(
  provider: string,
  id: string,
  name: string,
  baseUrl: string,
  extraCompat: Record<string, unknown> = {},
): Model<"openai-completions"> {
  return {
    id,
    name,
    api: "openai-completions",
    provider,
    baseUrl,
    reasoning: false,
    input: ["text"],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    contextWindow: 128000,
    maxTokens: 32000,
    // Non-standard OpenAI service: use the system role and do not send reasoning_effort/store
    compat: {
      supportsDeveloperRole: false,
      supportsReasoningEffort: false,
      supportsStore: false,
      ...extraCompat,
    },
  };
}

export function buildModels(config: Config): Models {
  const models = createModels();

  models.setProvider(
    createProvider({
      id: "deepseek",
      name: "DeepSeek",
      baseUrl: config.deepseekBaseUrl,
      auth: { apiKey: envApiKeyAuth("DeepSeek API key", ["DEEPSEEK_API_KEY"]) },
      models: [
        openAIModel("deepseek", config.deepseekModel, "DeepSeek chat", config.deepseekBaseUrl),
      ],
      api: openAICompletionsApi(),
    }),
  );

  models.setProvider(
    createProvider({
      id: "relay",
      name: "Relay service",
      baseUrl: config.relayBaseUrl,
      auth: { apiKey: envApiKeyAuth("Relay service API key", ["RELAY_API_KEY"]) },
      models: [
        openAIModel("relay", config.relayModel, "Relay chat", config.relayBaseUrl, {
          supportsUsageInStreaming: false,
        }),
      ],
      api: openAICompletionsApi(),
    }),
  );

  return models;
}

/** Get the default chat model (DeepSeek). */
export function getMainModel(models: Models, config: Config): Model<"openai-completions"> {
  const m = models.getModel("deepseek", config.deepseekModel);
  if (!m) throw new Error(`DeepSeek model not found: ${config.deepseekModel}`);
  return m as Model<"openai-completions">;
}
