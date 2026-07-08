/**
 * 会话管理 - 后端 API 驱动
 * 所有会话数据存储在后端 SQLite，前端只做 API 调用和缓存。
 */

import {
  createSession as apiCreateSession,
  listSessions as apiListSessions,
  getSession as apiGetSession,
  deleteSession as apiDeleteSession,
  type SessionInfo,
  type SessionDetail,
  type SessionMessage,
} from "./api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: { title: string; chunk_index: number; content_preview: string }[];
  timestamp: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

const ACTIVE_KEY = "papermind_active_conversation";

// --- Session → Conversation 转换 ---

function sessionToConversation(session: SessionDetail): Conversation {
  return {
    id: session.id,
    title: session.title,
    messages: session.messages.map(msgToMessage),
    createdAt: session.created_at,
    updatedAt: session.updated_at,
  };
}

function msgToMessage(msg: SessionMessage): Message {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    sources: msg.sources || [],
    timestamp: msg.created_at,
  };
}

// --- Public API ---

export async function getConversations(): Promise<Conversation[]> {
  try {
    const sessions = await apiListSessions();
    return sessions.map((s: SessionInfo) => ({
      id: s.id,
      title: s.title,
      messages: [],  // 列表模式不加载消息
      createdAt: s.created_at,
      updatedAt: s.updated_at,
    }));
  } catch {
    return [];
  }
}

export async function getConversation(id: string): Promise<Conversation | undefined> {
  try {
    const session = await apiGetSession(id);
    return sessionToConversation(session);
  } catch {
    return undefined;
  }
}

export async function createConversation(): Promise<Conversation> {
  const session = await apiCreateSession();
  return {
    id: session.id,
    title: session.title,
    messages: [],
    createdAt: session.created_at,
    updatedAt: session.created_at,
  };
}

export async function deleteConversation(id: string): Promise<void> {
  await apiDeleteSession(id);
  if (getActiveConversationId() === id) {
    setActiveConversationId(null);
  }
}

// --- Active conversation tracking (still localStorage for quick UI) ---

export function getActiveConversationId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_KEY);
}

export function setActiveConversationId(id: string | null) {
  if (id) {
    localStorage.setItem(ACTIVE_KEY, id);
  } else {
    localStorage.removeItem(ACTIVE_KEY);
  }
}
