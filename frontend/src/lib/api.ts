/**
 * PaperMind API Client
 * 与 FastAPI 后端通信，所有需要认证的接口通过 authFetch 自动带上 JWT token。
 */

import { getToken, setAuth } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ========== Auth Fetch Helper ==========

/** 带 Authorization header 的 fetch 封装 */
async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  return fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
}

// ========== Types ==========

export interface PaperInfo {
  title: string;
  authors: string;
  chunks: number;
  source: string;
  venue: string;
}

export interface PaperListResponse {
  papers: PaperInfo[];
  total: number;
  total_chunks: number;
}

export interface ChatResponse {
  answer: string;
  sources: {
    title: string;
    chunk_index: number;
    content_preview: string;
  }[];
  session_id?: string;
  rewritten_query?: string;
}

export interface SearchResult {
  content: string;
  title: string;
  authors: string;
  chunk_index: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

export interface SessionInfo {
  id: string;
  title: string;
  updated_at: string;
  created_at: string;
  message_count: number;
}

export interface SessionMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  sources: { title: string; chunk_index: number; content_preview: string }[];
  created_at: string;
}

export interface SessionDetail {
  id: string;
  title: string;
  summary: string;
  created_at: string;
  updated_at: string;
  messages: SessionMessage[];
}

// ========== Auth ==========

export interface AuthResponse {
  token: string;
  user: { id: string; username: string };
}

export async function register(username: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "注册失败" }));
    throw new Error(err.detail || "注册失败");
  }
  const data: AuthResponse = await res.json();
  setAuth(data.token, data.user);
  return data;
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "登录失败" }));
    throw new Error(err.detail || "登录失败");
  }
  const data: AuthResponse = await res.json();
  setAuth(data.token, data.user);
  return data;
}

export async function getMe(): Promise<{ id: string; username: string; email: string | null; created_at: string }> {
  const res = await authFetch(`${API_BASE}/api/auth/me`);
  if (!res.ok) throw new Error("获取用户信息失败");
  return res.json();
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/auth/password`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "修改失败" }));
    throw new Error(err.detail || "修改失败");
  }
}

export async function updateProfile(username?: string, email?: string): Promise<AuthResponse> {
  const res = await authFetch(`${API_BASE}/api/auth/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "更新失败" }));
    throw new Error(err.detail || "更新失败");
  }
  const data: AuthResponse = await res.json();
  setAuth(data.token, data.user);
  return data;
}

// ========== Sessions ==========

export async function createSession(): Promise<{ id: string; title: string; created_at: string }> {
  const res = await authFetch(`${API_BASE}/api/sessions`, { method: "POST" });
  if (!res.ok) throw new Error("创建会话失败");
  return res.json();
}

export async function listSessions(): Promise<SessionInfo[]> {
  const res = await authFetch(`${API_BASE}/api/sessions`);
  if (!res.ok) throw new Error("获取会话列表失败");
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await authFetch(`${API_BASE}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error("获取会话详情失败");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/sessions/${sessionId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "删除会话失败");
  }
}

// ========== Papers ==========

export async function uploadPaper(file: File, title?: string): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);

  const res = await authFetch(`${API_BASE}/api/papers/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "上传失败");
  }
  return res.json();
}

export async function listPapers(): Promise<PaperListResponse> {
  const res = await authFetch(`${API_BASE}/api/papers`);
  if (!res.ok) throw new Error("获取论文列表失败");
  return res.json();
}

export async function deletePaper(title: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/papers/${encodeURIComponent(title)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "删除失败");
  }
}

export function getPaperPdfUrl(title: string): string {
  // PDF 流式下载需要带 token，通过 query param 传递（浏览器直接 src 不能设 header）
  const token = getToken();
  const base = `${API_BASE}/api/papers/${encodeURIComponent(title)}/pdf`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

// ========== Annotations ==========

export interface AnnotationRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Annotation {
  id: string;
  paper_title: string;
  page: number;
  text: string;
  note: string;
  color: string;
  type: "highlight" | "underline" | "strikethrough";
  rects: AnnotationRect[];
  created_at: string;
}

export async function getAnnotations(paperTitle: string): Promise<{ annotations: Annotation[] }> {
  const res = await authFetch(`${API_BASE}/api/annotations/${encodeURIComponent(paperTitle)}`);
  if (!res.ok) throw new Error("获取标注失败");
  return res.json();
}

export async function createAnnotation(data: {
  paper_title: string;
  page: number;
  text: string;
  note?: string;
  color: string;
  type: "highlight" | "underline" | "strikethrough";
  rects: AnnotationRect[];
}): Promise<Annotation> {
  const res = await authFetch(`${API_BASE}/api/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("创建标注失败");
  return res.json();
}

export async function updateAnnotation(id: string, data: { note?: string; color?: string }): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/annotations/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("更新标注失败");
}

export async function deleteAnnotation(id: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/annotations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除标注失败");
}

// ========== Chat ==========

export async function chat(
  question: string,
  sessionId?: string,
  k: number = 5
): Promise<ChatResponse> {
  const res = await authFetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId, k }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "问答失败");
  }
  return res.json();
}

// ========== Chat Stream (SSE) ==========

export interface StreamCallbacks {
  onSources: (sources: ChatResponse["sources"]) => void;
  onToken: (token: string) => void;
  onDone: (fullAnswer: string) => void;
  onError: (error: Error) => void;
}

export async function chatStream(
  sessionId: string,
  question: string,
  callbacks: StreamCallbacks,
  k: number = 5,
  paperTitle?: string,
  paperTitles?: string[],
): Promise<void> {
  // SSE 用 authFetch（fetch + Authorization header）
  const res = await authFetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      k,
      paper_title: paperTitle,
      paper_titles: paperTitles && paperTitles.length > 0 ? paperTitles : undefined,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "流式请求失败" }));
    callbacks.onError(new Error(err.detail || "流式请求失败"));
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;

        try {
          const event = JSON.parse(trimmed.slice(6));
          if (event.type === "sources") callbacks.onSources(event.data);
          else if (event.type === "token") callbacks.onToken(event.data);
          else if (event.type === "done") callbacks.onDone(event.data);
          else if (event.type === "error") callbacks.onError(new Error(event.data));
        } catch {
          // skip malformed events
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error("流式读取失败"));
  }
}

// ========== Search ==========

export async function search(query: string, k: number = 5): Promise<SearchResponse> {
  const res = await authFetch(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, k }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "搜索失败");
  }
  return res.json();
}

// ========== Knowledge Graph ==========

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export async function getGraph(): Promise<GraphData> {
  const res = await authFetch(`${API_BASE}/api/graph`);
  if (!res.ok) throw new Error("获取图谱失败");
  return res.json();
}

export async function getPaperGraph(title: string): Promise<GraphData> {
  const res = await authFetch(`${API_BASE}/api/graph/paper/${encodeURIComponent(title)}`);
  if (!res.ok) throw new Error("获取论文图谱失败");
  return res.json();
}

export async function getGraphStats(): Promise<Record<string, any>> {
  const res = await authFetch(`${API_BASE}/api/graph/stats`);
  if (!res.ok) throw new Error("获取图谱统计失败");
  return res.json();
}

export async function getKeywordGraph(): Promise<GraphData> {
  const res = await authFetch(`${API_BASE}/api/graph/keywords`);
  if (!res.ok) throw new Error("获取关键词图谱失败");
  return res.json();
}

export async function getPapersGraph(titles: string[]): Promise<GraphData> {
  const res = await authFetch(`${API_BASE}/api/graph/papers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titles }),
  });
  if (!res.ok) throw new Error("获取多论文图谱失败");
  return res.json();
}

export async function getConcepts(): Promise<{ concepts: string[] }> {
  const res = await authFetch(`${API_BASE}/api/graph/concepts`);
  if (!res.ok) throw new Error("获取概念失败");
  return res.json();
}

export interface PaperWithConcepts {
  title: string;
  authors: string;
  concepts: string[];
}

export async function getPapersWithConcepts(): Promise<{ papers: PaperWithConcepts[] }> {
  const res = await authFetch(`${API_BASE}/api/graph/papers-with-concepts`);
  if (!res.ok) throw new Error("获取论文概念失败");
  return res.json();
}

export interface ConceptFrequency {
  name: string;
  count: number;
}

export async function getConceptFrequency(): Promise<{ concepts: ConceptFrequency[] }> {
  const res = await authFetch(`${API_BASE}/api/graph/concept-frequency`);
  if (!res.ok) throw new Error("获取概念频率失败");
  return res.json();
}

export async function getMethodEvolution(): Promise<{ relations: { from: string; to: string }[] }> {
  const res = await authFetch(`${API_BASE}/api/graph/method-evolution`);
  if (!res.ok) throw new Error("获取方法演进失败");
  return res.json();
}

export async function getProblemsSolutions(): Promise<{ data: { paper: string; problem: string }[] }> {
  const res = await authFetch(`${API_BASE}/api/graph/problems-solutions`);
  if (!res.ok) throw new Error("获取问题解决方案失败");
  return res.json();
}

export async function reextractGraph(title: string): Promise<{
  status: string;
  message: string;
  methods: number;
  concepts: number;
  relations: number;
}> {
  const res = await authFetch(`${API_BASE}/api/graph/extract/${encodeURIComponent(title)}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "重新提取失败" }));
    throw new Error(err.detail || "重新提取失败");
  }
  return res.json();
}

export interface UploadDay {
  date: string;
  label: string;
  count: number;
}

export async function getUploadHistory(): Promise<{ days: UploadDay[] }> {
  const res = await authFetch(`${API_BASE}/api/papers/upload-history`);
  if (!res.ok) throw new Error("获取上传历史失败");
  return res.json();
}

// ========== Paper Status ==========

export type PaperStatus = "unread" | "reading" | "read";

export async function getAllPaperStatuses(): Promise<{ statuses: Record<string, PaperStatus> }> {
  const res = await authFetch(`${API_BASE}/api/papers/statuses`);
  if (!res.ok) throw new Error("获取论文状态失败");
  return res.json();
}

export async function updatePaperStatus(title: string, status: PaperStatus): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/papers/${encodeURIComponent(title)}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("更新论文状态失败");
}

// ========== Recommend ==========

export interface RecommendedPaper {
  title: string;
  authors: string[];
  year: number | null;
  venue: string;
  url: string;
  ccf_level: string | null;
}

export async function getRecommendations(
  range: string = "1year",
  level: string = "all"
): Promise<{ papers: RecommendedPaper[]; keywords: string[] }> {
  const res = await authFetch(`${API_BASE}/api/recommend?range=${range}&level=${level}`);
  if (!res.ok) throw new Error("获取推荐失败");
  return res.json();
}

// ========== Self-Growing Memory ==========

export interface MemoryItem {
  id: string;
  knowledge: string;
  topics: string[];
  source_papers: string[];
  source_session: string | null;
  importance: number;
  status: string;
  created_at: string;
  last_accessed: string;
  access_count: number;
  times_used: number;
}

export interface MemoryStatus {
  count: number;
  has_profile: boolean;
  available: boolean;
}

export interface MemoryProfile {
  profile: string | null;
  interaction_count?: number;
  updated_at?: string;
  message?: string;
}

export interface KnowledgeTreeNode {
  name: string;
  type: string;
  mastery: "mastered" | "learning" | "unexplored";
  query_count: number;
  last_queried: string | null;
}

export interface KnowledgeTreeOverview {
  unlocked: boolean;
  reason?: string;
  paper_count?: number;
  memory_count?: number;
  nodes?: KnowledgeTreeNode[];
  summary?: { mastered: number; learning: number; unexplored: number };
  total?: number;
}

export async function getMemoryStatus(): Promise<MemoryStatus> {
  const res = await authFetch(`${API_BASE}/api/memory/status`);
  if (!res.ok) throw new Error("获取记忆库状态失败");
  return res.json();
}

export async function getMemoryItems(
  limit: number = 50,
  offset: number = 0
): Promise<{ items: MemoryItem[]; total: number }> {
  const res = await authFetch(`${API_BASE}/api/memory/items?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error("获取记忆列表失败");
  return res.json();
}

export async function deleteMemoryItem(id: string): Promise<void> {
  const res = await authFetch(`${API_BASE}/api/memory/items/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "删除记忆失败" }));
    throw new Error(err.detail || "删除记忆失败");
  }
}

export async function getMemoryProfile(): Promise<MemoryProfile> {
  const res = await authFetch(`${API_BASE}/api/memory/profile`);
  if (!res.ok) throw new Error("获取用户画像失败");
  return res.json();
}

export async function refreshMemoryProfile(): Promise<MemoryProfile> {
  const res = await authFetch(`${API_BASE}/api/memory/refresh-profile`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "画像刷新失败" }));
    throw new Error(err.detail || "画像刷新失败");
  }
  return res.json();
}

export async function getKnowledgeTree(): Promise<KnowledgeTreeOverview> {
  const res = await authFetch(`${API_BASE}/api/memory/knowledge-tree`);
  if (!res.ok) throw new Error("获取知识树失败");
  return res.json();
}

// ========== User Interest Graph ==========

export interface InterestGraphNode {
  name: string;
  type: "Field" | "Topic" | "Entity";
  description: string;
  weight: number;
  hit_count: number;
  first_seen: string;
  last_seen: string;
  status: string;
}

export interface InterestGraphEdge {
  source: string;
  target: string;
  type: "CONTAINS" | "RELATES_TO" | "COMPARES_WITH";
  description: string;
  weight: number;
  confidence: number;
}

export interface InterestGraphData {
  nodes: InterestGraphNode[];
  edges: InterestGraphEdge[];
}

export interface InterestGraphHealth {
  available: boolean;
  total_active_nodes?: number;
  total_dormant_nodes?: number;
  total_relations?: number;
  field_count?: number;
  topic_count?: number;
  entity_count?: number;
  orphan_rate?: number;
  avg_connectivity?: number;
}

export interface GraphSummaryField {
  name: string;
  description: string;
  weight: number;
  children: {
    name: string;
    type: string;
    description: string;
    weight: number;
    children: { name: string; description: string; weight: number }[];
  }[];
}

export interface GrowthLogEntry {
  id: string;
  event_type: string;
  detail: Record<string, unknown>;
  source: string;
  created_at: string;
}

export async function getInterestGraph(status: string = "active"): Promise<InterestGraphData> {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph?status=${status}`);
  if (!res.ok) throw new Error("获取兴趣图谱失败");
  return res.json();
}

export async function getInterestGraphNode(name: string) {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/node/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error("获取节点详情失败");
  return res.json();
}

export async function patchInterestGraphNode(name: string, data: { description?: string; type?: string }) {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/node/${encodeURIComponent(name)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("修改节点失败");
  return res.json();
}

export async function deleteInterestGraphNode(name: string) {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/node/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("删除节点失败");
  return res.json();
}

export async function restoreInterestGraphNode(name: string) {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/node/${encodeURIComponent(name)}/restore`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("恢复节点失败");
  return res.json();
}

export async function mergeInterestGraphNodes(keepName: string, removeName: string) {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keep_name: keepName, remove_name: removeName }),
  });
  if (!res.ok) throw new Error("合并节点失败");
  return res.json();
}

export async function rebuildInterestGraph() {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/rebuild`, { method: "POST" });
  if (!res.ok) throw new Error("结构审视失败");
  return res.json();
}

export async function getInterestGraphSummary(): Promise<{ summary: GraphSummaryField[] }> {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/summary`);
  if (!res.ok) throw new Error("获取方向摘要失败");
  return res.json();
}

export async function getInterestGraphStats(): Promise<InterestGraphHealth> {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/stats`);
  if (!res.ok) throw new Error("获取图谱统计失败");
  return res.json();
}

export async function getInterestGraphHealth(): Promise<InterestGraphHealth> {
  const res = await authFetch(`${API_BASE}/api/memory/interest-graph/health`);
  if (!res.ok) throw new Error("获取健康度失败");
  return res.json();
}

export async function getGrowthLog(limit: number = 20): Promise<{ logs: GrowthLogEntry[] }> {
  const res = await authFetch(`${API_BASE}/api/memory/growth-log?limit=${limit}`);
  if (!res.ok) throw new Error("获取生长日志失败");
  return res.json();
}
