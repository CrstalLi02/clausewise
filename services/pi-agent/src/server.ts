/**
 * Fastify HTTP server: exposes /answer and /loop/run for the Python backend (or frontend).
 */
import Fastify, { type FastifyInstance } from "fastify";
import type { Config } from "./config.js";
import type { Runtime } from "./runtime.js";
import { answer } from "./orchestrator.js";
import { runLoop } from "./loop.js";
import { executeAgent, type AgentType } from "./agents.js";
import { timingSafeEqual } from "node:crypto";

const AGENT_TYPES = new Set<AgentType>(["intent", "rewrite", "answer", "verify", "reflect"]);
const TOOL_NAMES = new Set([
  "retrieve_documents", "lookup_calendar", "list_departments", "get_glossary",
  "submit_feedback", "list_pending_feedback", "save_skill", "save_hook", "save_rule",
]);

function internalAuthorized(config: Config, header: string | string[] | undefined): boolean {
  if (!config.internalApiToken || typeof header !== "string") return false;
  // Fail immediately if lengths differ; otherwise use timingSafeEqual to avoid timing leaks of the shared token.
  const expected = Buffer.from(config.internalApiToken);
  const supplied = Buffer.from(header);
  return expected.length === supplied.length && timingSafeEqual(expected, supplied);
}

export function buildApp(config: Config, runtime: Runtime): FastifyInstance {
  const app = Fastify({ logger: false });

  app.get("/health", async () => ({ status: "ok", service: "clausewise-pi-agent" }));

  app.post("/v1/agent/run", async (req, reply) => {
    if (!internalAuthorized(config, req.headers["x-internal-token"])) {
      return reply.code(config.internalApiToken ? 401 : 503).send({
        code: 1, message: config.internalApiToken ? "Invalid internal service token" : "Internal service token is not configured",
      });
    }
    const body = (req.body ?? {}) as {
      agentType?: AgentType;
      systemPrompt?: string;
      prompt?: string;
      outputMode?: "text" | "json";
      allowedTools?: string[];
      timeoutMs?: number;
      traceId?: string;
    };
    if (!body.agentType || !AGENT_TYPES.has(body.agentType)) {
      return reply.code(400).send({ code: 1, message: "Invalid agentType" });
    }
    if (!body.systemPrompt || !body.prompt) {
      return reply.code(400).send({ code: 1, message: "systemPrompt and prompt are required" });
    }
    if (body.systemPrompt.length > 32_000 || body.prompt.length > 128_000) {
      return reply.code(413).send({ code: 1, message: "Agent prompt exceeds the size limit" });
    }
    const outputMode = body.outputMode === "text" ? "text" : "json";
    const allowedTools = (body.allowedTools ?? []).filter((name) => TOOL_NAMES.has(name));
    const timeoutMs = Math.max(250, Math.min(Number(body.timeoutMs ?? 30_000), 120_000));
    try {
      const execution = executeAgent(
        runtime.runtime, body.agentType, body.systemPrompt, body.prompt, outputMode, allowedTools,
      );
      let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
      const timeout = new Promise<never>((_, reject) => {
        timeoutHandle = setTimeout(() => reject(new Error(`pi agent timeout after ${timeoutMs}ms`)), timeoutMs);
      });
      const result = await Promise.race([execution, timeout]).finally(() => {
        if (timeoutHandle) clearTimeout(timeoutHandle);
      });
      return {
        code: 0, message: "ok",
        data: { ...result, traceId: body.traceId ?? "", allowedTools },
      };
    } catch (err) {
      req.log.error(err);
      return reply.code(502).send({ code: 1, message: String(err) });
    }
  });

  app.post("/answer", async (req, reply) => {
    if (!internalAuthorized(config, req.headers["x-internal-token"])) {
      return reply.code(config.internalApiToken ? 401 : 503).send({ code: 1, message: "Internal service not authorized" });
    }
    const body = (req.body ?? {}) as {
      query?: string;
      sessionId?: string;
      userId?: string;
      deptIds?: string[] | null;
    };
    if (!body.query) {
      return reply.code(400).send({ code: 1, message: "query is required" });
    }
    try {
      const result = await answer(runtime.runtime, config, {
        query: body.query,
        sessionId: body.sessionId,
        userId: body.userId ?? "anonymous",
        deptIds: body.deptIds ?? null,
      });
      console.log(`[pi-agent] /answer handled: "${body.query.slice(0, 40)}" -> ${result.answer.length} chars, intent=${result.intentType}`);
      return { code: 0, message: "ok", data: result };
    } catch (err) {
      req.log.error(err);
      return reply.code(500).send({ code: 1, message: String(err) });
    }
  });

  app.post("/loop/run", async (req, reply) => {
    if (!internalAuthorized(config, req.headers["x-internal-token"])) {
      return reply.code(config.internalApiToken ? 401 : 503).send({ code: 1, message: "Internal service not authorized" });
    }
    const data = await runLoop(runtime.runtime, config);
    return { code: 0, message: "ok", data };
  });

  return app;
}
