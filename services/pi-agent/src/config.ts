/**
 * Centralized config: read from environment variables (injected by compose in Docker; use .env locally).
 * DeepSeek is the primary chat model; the relay service (OpenAI-compatible) is used for non-DeepSeek models (bge reranker, etc.).
 */

function str(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

function num(name: string, fallback: number): number {
  const v = process.env[name];
  if (v === undefined || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export interface Config {
  port: number;
  host: string;
  backendUrl: string;
  /** Shared token required to call the backend /internal/* (matches the backend INTERNAL_API_TOKEN) */
  internalApiToken: string;

  deepseekApiKey: string;
  deepseekBaseUrl: string;
  deepseekModel: string;

  relayApiKey: string;
  relayBaseUrl: string;
  relayModel: string;

  loopEnabled: boolean;
  loopPhase: "human_in_loop" | "human_on_loop" | "human_out_of_loop";
  hookHighConfidence: number;
}

export function loadConfig(): Config {
  return {
    port: num("PORT", 8100),
    host: str("HOST", "0.0.0.0"),
    backendUrl: str("BACKEND_URL", "http://localhost:8000"),
    internalApiToken: str("INTERNAL_API_TOKEN", ""),

    deepseekApiKey: str("DEEPSEEK_API_KEY", ""),
    deepseekBaseUrl: str("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    deepseekModel: str("DEEPSEEK_MODEL", "deepseek-v4-flash"),

    relayApiKey: str("RELAY_API_KEY", ""),
    relayBaseUrl: str("RELAY_BASE_URL", "https://yunwu.ai/v1"),
    relayModel: str("RELAY_MODEL", "gpt-5.5"),

    loopEnabled: str("LOOP_ENABLED", "true") === "true",
    loopPhase: (str("LOOP_PHASE", "human_on_loop") as Config["loopPhase"]),
    hookHighConfidence: num("HOOK_HIGH_CONFIDENCE", 0.9),
  };
}
