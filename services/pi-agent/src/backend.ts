/**
 * Python backend HTTP client: the pi service uses it to access data/retrieval/storage (separation of frontend/backend/module responsibilities).
 */
import type { Config } from "./config.js";

interface ApiResponse {
  code?: number;
  message?: string;
  data?: unknown;
}

export async function backendFetch(
  config: Config,
  path: string,
  options: RequestInit = {},
): Promise<unknown> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (config.internalApiToken) {
    headers["X-Internal-Token"] = config.internalApiToken;
  }
  const resp = await fetch(`${config.backendUrl}${path}`, {
    ...options,
    headers,
  });
  const body = (await resp.json().catch(() => ({}))) as ApiResponse;
  if (!resp.ok || (body.code ?? 0) !== 0) {
    throw new Error(`backend ${path} failed (${resp.status}): ${body.message ?? "unknown"}`);
  }
  return body.data;
}

export interface Chunk {
  _id: string;
  doc_id: string;
  dept_id: string;
  chunk_index: number;
  section_path: string[];
  section_title: string;
  content: string;
  doc_title?: string;
  score?: number;
}

export async function retrieveChunks(
  config: Config,
  query: string,
  deptIds: string[] | null,
  topK = 5,
): Promise<Chunk[]> {
  const data = await backendFetch(config, "/api/v1/internal/retrieve", {
    method: "POST",
    body: JSON.stringify({ query, dept_ids: deptIds, top_k: topK }),
  });
  return (data as Chunk[]) ?? [];
}

export async function listDepartments(config: Config): Promise<Array<{ _id: string; name: string }>> {
  return ((await backendFetch(config, "/api/v1/internal/departments")) as Array<{ _id: string; name: string }>) ?? [];
}

export async function getCalendar(config: Config): Promise<unknown> {
  return backendFetch(config, "/api/v1/internal/calendar");
}

export async function getGlossary(config: Config): Promise<unknown> {
  return backendFetch(config, "/api/v1/internal/glossary");
}

export async function listPendingFeedback(config: Config): Promise<unknown> {
  return backendFetch(config, "/api/v1/internal/feedback/pending");
}

export async function submitFeedback(
  config: Config,
  payload: { query: string; answer: string; signal: string },
): Promise<void> {
  await backendFetch(config, "/api/v1/internal/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveArtifact(
  config: Config,
  payload: Record<string, unknown>,
): Promise<unknown> {
  return backendFetch(config, "/api/v1/internal/artifacts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
