/**
 * PaperMind API Client
 * 与 FastAPI 后端通信
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ========== Types ==========

export interface PaperInfo {
  title: string;
  authors: string;
  chunks: number;
  source: string;
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

// ========== Sessions ==========

export async function createSession(): Promise<{ id: string; title: string; created_at: string }> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("创建会话失败");
  return res.json();
}

export async function listSessions(): Promise<SessionInfo[]> {
  const res = await fetch(`${API_BASE}/api/sessions`);
  if (!res.ok) throw new Error("获取会话列表失败");
  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`);
  if (!res.ok) throw new Error("获取会话详情失败");
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
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

  const res = await fetch(`${API_BASE}/api/papers/upload`, {
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
  const res = await fetch(`${API_BASE}/api/papers`);
  if (!res.ok) throw new Error("获取论文列表失败");
  return res.json();
}

export async function deletePaper(title: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/papers/${encodeURIComponent(title)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "删除失败");
  }
}

// ========== Chat ==========

export async function chat(
  question: string,
  sessionId?: string,
  k: number = 5
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
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
  k: number = 5
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId, k }),
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

          if (event.type === "sources") {
            callbacks.onSources(event.data);
          } else if (event.type === "token") {
            callbacks.onToken(event.data);
          } else if (event.type === "done") {
            callbacks.onDone(event.data);
          } else if (event.type === "error") {
            callbacks.onError(new Error(event.data));
          }
        } catch {
          // Skip malformed events
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error("流式读取失败"));
  }
}

// ========== Search ==========

export async function search(query: string, k: number = 5): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/api/search`, {
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

// --- Knowledge Graph ---

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
  const res = await fetch(`${API_BASE}/api/graph`);
  if (!res.ok) throw new Error("获取图谱失败");
  return res.json();
}

export async function getPaperGraph(title: string): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/api/graph/paper/${encodeURIComponent(title)}`);
  if (!res.ok) throw new Error("获取论文图谱失败");
  return res.json();
}

export async function getGraphStats(): Promise<Record<string, any>> {
  const res = await fetch(`${API_BASE}/api/graph/stats`);
  if (!res.ok) throw new Error("获取图谱统计失败");
  return res.json();
}
