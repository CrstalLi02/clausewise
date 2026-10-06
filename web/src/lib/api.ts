/** Backend API types and call wrappers (proxied to the Python backend via Next.js rewrites). */

// ==================== Types ====================
export interface Citation {
  doc_id: string;
  doc_title: string;
  dept_id: string;
  chunk_index: number;
  section_path: string[];
  snippet: string;
}

export interface DeptRoute {
  dept_ids: string[];
  dept_names: string[];
  matched_by: string;
  confidence: number;
  reasons: string[];
}

export interface ChatResult {
  session_id: string;
  answer: string;
  citations: Citation[];
  dept_ids: string[];
  confidence: number;
  intent_type: string;
  verification: { passed: boolean; score: number; issues: string[] };
  retrieved_count: number;
  route?: DeptRoute | null;
}

/** Past session summary (an item in the "Recent" sidebar list). */
export interface SessionSummary {
  session_id: string;
  title: string;
  message_count: number;
  updated_at: string;
}

/** A single message in the session history. */
export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  query?: string;
}

export interface Department {
  _id: string;
  name: string;
  name_en?: string;
  category?: string;
  admin_users?: string[];
  agent_config?: Record<string, unknown>;
  loop_phase?: string;
  review_stats?: { total: number; correct: number; accuracy: number };
  fade_out?: { achieved_at: string; accuracy: number; samples: number; reason: string } | null;
}

export interface User {
  id: string;
  username: string;
  name: string;
  role: "student" | "admin";
  dept_id: string;
}

export interface PipelineStage {
  key: string;
  name: string;
  done: boolean;
  detail?: string;
}

export interface Document {
  _id: string;
  dept_id: string;
  title: string;
  doc_type: string;
  version?: string;
  status: string;
  effective_date?: string | null;
  tags?: string[];
  chunk_count?: number;
  vector_status?: string;
  applicable_scope?: string[];
  cross_refs?: string[];
  pipeline_stages?: PipelineStage[];
  source?: { file_name: string; uploaded_by: string; uploaded_at: string };
  created_at?: string;
  updated_at?: string;
  chunks?: unknown[];
}

export interface QAItem {
  question: string;
  expected: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  verdict: string | null;
  correct: boolean | null;
  correction: string;
}

export interface ReviewOrder {
  _id: string;
  dept_id: string;
  doc_id: string;
  doc_title: string;
  status: string;
  qa_pairs: QAItem[];
  total: number;
  correct: number;
  accuracy: number | null;
  created_at: string;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
}

export interface Skill {
  _id: string;
  name: string;
  dept_id?: string;
  scope?: string;
  trigger?: { intent_patterns?: string[]; confidence_threshold?: number };
  action?: Record<string, unknown>;
  metrics?: { trigger_count?: number; success_rate?: number; avg_latency_ms?: number };
  version?: number;
  status?: string;
  auto_generated?: boolean;
  confidence?: number;
  created_by?: string;
  created_at?: string;
  unique_rules?: string[];
  rubric_rules?: string[];
  description?: string;
  origin?: string;
  gray_percent?: number;
  replay?: { baseline_score?: number; candidate_score?: number; delta?: number; passed?: boolean };
}

export interface Hook {
  _id: string;
  name: string;
  scope?: string;
  trigger?: Record<string, unknown>;
  action?: Record<string, unknown>;
  confidence?: number;
  status?: string;
  auto_generated?: boolean;
}

export interface Rule {
  _id: string;
  name: string;
  scope?: string;
  content?: string;
  priority?: number;
  status?: string;
  auto_generated?: boolean;
}

export interface AgentInfo {
  _id: string;
  name: string;
  name_en?: string;
  model: string;
  temperature: number;
  agent_config: Record<string, unknown>;
  loop_phase: string;
  review_stats: { total: number; correct: number; accuracy: number };
  doc_count: number;
  skill_count: number;
  hook_count: number;
  hot_queries: { q: string; n: number }[];
  replicas: number;
}

export interface MemoryPlaneInsight {
  key: "working" | "episodic" | "user" | "organization" | "learning";
  name: string;
  count: number;
  detail: string;
  store: string;
}

export interface SystemInsights {
  memory_planes: MemoryPlaneInsight[];
  fact_plane: {
    documents: number;
    active_documents: number;
    chunks: number;
    relations: number;
    conflicts: number;
  };
  governance: { usage_records: number; stale_org_memory: number; pending_candidates: number };
  evolution: {
    strategy_versions: number;
    executions: number;
    experiments: Array<Record<string, unknown>>;
    proposals: Array<Record<string, unknown>>;
    treatment: number;
    control: number;
  };
  signals: Record<string, number>;
  recent_traces: Array<{
    id: string; query: string; latency_ms: number; success: boolean; intent: string; created_at: string;
  }>;
}

export interface UserMemoryItem {
  _id: string;
  key: string;
  value: unknown;
  category: string;
  source_type?: string;
  revision?: number;
  created_at?: string;
  expires_at?: string;
}

export interface Dashboard {
  loop_phase_global: string;
  loop_enabled: boolean;
  thresholds: Record<string, number>;
  departments: Array<
    Department & {
      doc_count: number;
      chunk_count: number;
      skill_count: number;
      conflict_count: number;
    }
  >;
  skills: Skill[];
  hooks: Hook[];
  rules: Rule[];
  feedback: { total: number; up: number; down: number; adoption_rate: number };
  trace_count: number;
  pending_review_count: number;
  test_question_count: number;
}

interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

// ==================== Auth token storage ====================
const TOKEN_KEY = "clausewise_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

// ==================== Request wrapper ====================
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(path, { ...options, headers });
  let json: ApiResponse<T> | { detail?: string } = { code: -1, message: "Request failed", data: null as unknown as T };
  try {
    json = (await resp.json()) as ApiResponse<T>;
  } catch {
    /* ignore parse error */
  }
  if (!resp.ok) {
    const detail = (json as { detail?: string }).detail;
    throw new Error(detail || `HTTP ${resp.status}`);
  }
  if (json && typeof json === "object" && "code" in json && (json as ApiResponse<T>).code !== 0) {
    throw new Error((json as ApiResponse<T>).message || "Request failed");
  }
  return (json as ApiResponse<T>).data;
}

// ==================== Auth ====================
export async function login(username: string, password: string): Promise<{ token: string; user: User }> {
  return request<{ token: string; user: User }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function me(): Promise<User> {
  return request<User>("/api/v1/auth/me");
}

// ==================== Q&A ====================
export async function listDepartments(): Promise<Department[]> {
  return request<Department[]>("/api/v1/departments");
}

export async function askQuestion(payload: {
  query: string;
  session_id: string | null;
  dept_ids: string[] | null;
}): Promise<ChatResult> {
  return request<ChatResult>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      query: payload.query,
      session_id: payload.session_id,
      dept_ids: payload.dept_ids,
    }),
  });
}

/** Submit explicit feedback (thumbs-up 👍 / thumbs-down 👎 / correction), counted toward the answer adoption rate. */
export async function submitFeedback(payload: {
  session_id: string;
  query: string;
  answer: string;
  signal: "up" | "down" | "correction";
}): Promise<{ received: string }> {
  return request<{ received: string }>("/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitImplicitFeedback(payload: {
  session_id: string;
  signal: "copy" | "follow_up" | "abandon";
  query?: string;
  answer?: string;
}): Promise<{ received: string }> {
  return request<{ received: string }>("/api/v1/feedback/implicit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ==================== Session history ("Recent" sidebar) ====================
/** List a user's past sessions (most recently active first). */
export async function listSessions(): Promise<SessionSummary[]> {
  return request<SessionSummary[]>("/api/v1/chat/sessions");
}

/** Read the full message history of a session. */
export async function sessionHistory(sessionId: string): Promise<HistoryMessage[]> {
  return request<HistoryMessage[]>(`/api/v1/chat/${sessionId}/history`);
}

/** Delete a session (also clearing working memory and persisted traces). */
export async function deleteSession(sessionId: string): Promise<{ cleared: string }> {
  return request<{ cleared: string }>(`/api/v1/chat/${sessionId}`, { method: "DELETE" });
}

// ==================== Documents ====================
export async function listDocuments(deptId?: string, status?: string): Promise<Document[]> {
  const q = new URLSearchParams();
  if (deptId) q.set("dept_id", deptId);
  if (status) q.set("status", status);
  const qs = q.toString();
  return request<Document[]>(`/api/v1/documents${qs ? "?" + qs : ""}`);
}

export async function getDocument(id: string): Promise<Document> {
  return request<Document>(`/api/v1/documents/${id}`);
}

export async function uploadDocument(
  file: File,
  deptId: string,
  uploadedBy = "admin"
): Promise<{ queued: boolean; job_id: string; file_name: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("dept_id", deptId);
  form.append("uploaded_by", uploadedBy);
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch("/api/v1/documents/upload", { method: "POST", headers, body: form });
  const json = (await resp.json()) as ApiResponse<{ queued: boolean; job_id: string; file_name: string }>;
  if (!resp.ok || json.code !== 0) throw new Error(json.message || "Upload failed");
  return json.data;
}

export interface AsyncJob {
  _id: string;
  type: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: { document_id?: string; relations?: number; review_id?: string; error?: string };
}

export interface LoopCycleReport {
  cycle_id: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  observed: number;
  bad_cases: number;
  signals: Record<string, number>;
  reflect: { root_causes?: Record<string, number>; suggestions?: Array<Record<string, unknown>> };
  adaptations: Array<{ type?: string; id?: string; name?: string; dept_id?: string; auto_activated?: boolean }>;
  deployed: { skills?: number; hooks?: number; rules?: number; rolled_back?: number };
  before: Record<string, number>;
  after: Record<string, number>;
  changes: Record<string, number>;
  summary: string;
  next_action: string;
  memory_retention?: Record<string, number>;
}

export interface LoopJob {
  _id: string;
  type: "run_loop";
  status: "queued" | "running" | "completed" | "failed";
  progress?: { stage?: string; detail?: string };
  result?: LoopCycleReport | { error?: string };
  created_at: string;
  updated_at: string;
}

export async function getUploadJob(jobId: string): Promise<AsyncJob> {
  return request<AsyncJob>(`/api/v1/documents/jobs/${jobId}`);
}

export async function updateDocumentStatus(id: string, status: string): Promise<{ doc_id: string; status: string }> {
  return request(`/api/v1/documents/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });
}

// ==================== Admin ====================
export async function dashboard(): Promise<Dashboard> {
  return request<Dashboard>("/api/v1/admin/dashboard");
}

export async function agents(): Promise<AgentInfo[]> {
  return request<AgentInfo[]>("/api/v1/admin/agents");
}

export async function listReviewOrders(deptId?: string, status?: string): Promise<ReviewOrder[]> {
  const q = new URLSearchParams();
  if (deptId) q.set("dept_id", deptId);
  if (status) q.set("status", status);
  const qs = q.toString();
  return request<ReviewOrder[]>(`/api/v1/admin/review/orders${qs ? "?" + qs : ""}`);
}

export async function getReviewOrder(id: string): Promise<ReviewOrder> {
  return request<ReviewOrder>(`/api/v1/admin/review/orders/${id}`);
}

export async function submitReview(
  id: string,
  verdicts: { index: number; correct: boolean; correction: string }[]
): Promise<ReviewOrder> {
  return request<ReviewOrder>(`/api/v1/admin/review/orders/${id}/submit`, {
    method: "POST",
    body: JSON.stringify({ verdicts }),
  });
}

export async function generateReview(docId: string): Promise<ReviewOrder | null> {
  return request<ReviewOrder | null>(`/api/v1/admin/documents/${docId}/review`, { method: "POST" });
}

export async function listSkills(status?: string): Promise<Skill[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<Skill[]>(`/api/v1/admin/skills${q}`);
}

export async function approveSkill(id: string): Promise<Skill> {
  return request<Skill>(`/api/v1/admin/skills/${id}/approve`, { method: "POST" });
}

export async function listHooks(): Promise<Hook[]> {
  return request<Hook[]>("/api/v1/admin/hooks");
}

export async function listRules(): Promise<Rule[]> {
  return request<Rule[]>("/api/v1/admin/rules");
}

export async function runLoop(): Promise<{ queued: boolean; job_id: string; status: string; message: string }> {
  return request<{ queued: boolean; job_id: string; status: string; message: string }>("/api/v1/admin/loop/run", { method: "POST" });
}

export async function getLoopJob(jobId: string): Promise<LoopJob> {
  return request<LoopJob>(`/api/v1/admin/loop/jobs/${jobId}`);
}

export async function listLoopJobs(limit = 10): Promise<LoopJob[]> {
  return request<LoopJob[]>(`/api/v1/admin/loop/jobs?limit=${limit}`);
}

export async function loopStats(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/v1/admin/loop/stats");
}

export async function pendingFeedback(): Promise<Record<string, unknown>[]> {
  return request<Record<string, unknown>[]>("/api/v1/admin/feedback/pending");
}

export async function listTraces(limit = 50): Promise<Record<string, unknown>[]> {
  return request<Record<string, unknown>[]>(`/api/v1/admin/traces?limit=${limit}`);
}

export async function systemInsights(): Promise<SystemInsights> {
  return request<SystemInsights>("/api/v1/admin/system-insights");
}

export async function setLoopPhase(phase: string): Promise<{ loop_phase: string }> {
  return request<{ loop_phase: string }>("/api/v1/admin/loop/phase", {
    method: "POST",
    body: JSON.stringify({ phase }),
  });
}

export async function createDepartment(payload: {
  id: string;
  name: string;
  name_en?: string;
  category?: string;
  admin_users?: string[];
}): Promise<Department> {
  return request<Department>("/api/v1/departments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function myMemories(): Promise<UserMemoryItem[]> {
  return request<UserMemoryItem[]>("/api/v1/memory/me");
}

export async function rememberForMe(payload: {
  key: string; value: unknown; category?: string; consent?: boolean;
}): Promise<UserMemoryItem> {
  return request<UserMemoryItem>("/api/v1/memory/me", {
    method: "POST",
    body: JSON.stringify({ ...payload, consent: payload.consent ?? true }),
  });
}

export async function forgetMemory(id: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/v1/memory/me/${id}`, { method: "DELETE" });
}

export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch("/healthz");
    return resp.ok;
  } catch {
    return false;
  }
}
