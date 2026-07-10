"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Brain, User, FileText, Sparkles, Plus, Trash2, MessageSquare, BookOpen, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { chatStream, listPapers, type PaperInfo } from "@/lib/api";
import {
  type Message,
  type Conversation,
  getConversations,
  getConversation,
  createConversation,
  deleteConversation,
  getActiveConversationId,
  setActiveConversationId,
} from "@/lib/conversations";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Paper filter state
  const [selectedPapers, setSelectedPapers] = useState<string[]>([]);
  const [allPapers, setAllPapers] = useState<PaperInfo[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState("");
  const pickerRef = useRef<HTMLDivElement>(null);
  const pickerBtnRef = useRef<HTMLButtonElement>(null);

  // Load conversations on mount
  useEffect(() => {
    async function load() {
      const all = await getConversations();
      setConversations(all);

      const savedId = getActiveConversationId();
      if (savedId && all.find((c) => c.id === savedId)) {
        setActiveId(savedId);
        const conv = await getConversation(savedId);
        if (conv) setMessages(conv.messages);
      }
    }
    load();
  }, []);

  // Load available papers for the picker
  useEffect(() => {
    listPapers().then((data) => setAllPapers(data.papers)).catch(() => {});
  }, []);

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return;
    const handle = (e: MouseEvent) => {
      if (
        pickerRef.current?.contains(e.target as Node) ||
        pickerBtnRef.current?.contains(e.target as Node)
      ) return;
      setPickerOpen(false);
      setPickerSearch("");
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [pickerOpen]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const refreshList = useCallback(async () => {
    const all = await getConversations();
    setConversations(all);
  }, []);

  const handleNewChat = async () => {
    const conv = await createConversation();
    setActiveId(conv.id);
    setActiveConversationId(conv.id);
    setMessages([]);
    await refreshList();
  };

  const handleSelectConversation = async (id: string) => {
    setActiveId(id);
    setActiveConversationId(id);
    const conv = await getConversation(id);
    setMessages(conv?.messages || []);
  };

  const handleDeleteConversation = async (id: string) => {
    await deleteConversation(id);
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
    await refreshList();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    // 如果没有活跃会话，自动创建一个
    let currentId = activeId;
    if (!currentId) {
      const conv = await createConversation();
      currentId = conv.id;
      setActiveId(currentId);
      setActiveConversationId(currentId);
      await refreshList();
    }

    // 乐观更新：先在 UI 上显示用户消息
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    const question = input.trim();
    setInput("");
    setIsLoading(true);

    // 创建空的 assistant 消息，后续逐步填充
    const assistantMsgId = crypto.randomUUID();
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      sources: [],
      timestamp: new Date().toISOString(),
    };
    setMessages([...newMessages, assistantMessage]);

    try {
      await chatStream(
        currentId,
        question,
        {
          onSources: (sources) => {
            setIsLoading(false);
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantMsgId ? { ...m, sources } : m))
            );
          },
          onToken: (token) => {
            setIsLoading(false);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: m.content + token } : m
              )
            );
          },
          onDone: (_fullAnswer) => {},
          onError: (error) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: `抱歉，出错了：${error.message}` }
                  : m
              )
            );
          },
        },
        5,
        undefined,                                          // paperTitle (single, for PDF viewer)
        selectedPapers.length > 0 ? selectedPapers : undefined, // paperTitles (multi, from picker)
      );
      await refreshList();
    } catch (error) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, content: `抱歉，出错了：${error instanceof Error ? error.message : "未知错误"}` }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="h-full flex">
      {/* Conversation List Sidebar */}
      <div className="w-64 border-r border-border bg-white flex flex-col shrink-0">
        <div className="p-3 border-b border-border">
          <button
            onClick={handleNewChat}
            className="w-full h-9 rounded-[10px] border border-border text-sm font-medium hover:bg-secondary transition-colors flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-0.5">
          {conversations.length === 0 ? (
            <p className="text-[12px] text-muted-foreground text-center py-8">
              No conversations yet
            </p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => handleSelectConversation(conv.id)}
                className={cn(
                  "group flex items-center gap-2 px-3 py-2 rounded-[10px] cursor-pointer transition-colors text-sm",
                  activeId === conv.id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )}
              >
                <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                <span className="flex-1 truncate text-[13px]">{conv.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteConversation(conv.id);
                  }}
                  className="w-5 h-5 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-all"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-auto">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
              <AnimatePresence initial={false}>
                {messages.map((msg) => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChatBubble message={msg} />
                  </motion.div>
                ))}
              </AnimatePresence>

              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-start gap-3"
                >
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <Brain className="w-4 h-4 text-primary" />
                  </div>
                  <div className="flex gap-1 pt-3">
                    <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-border bg-white p-4">
          <div className="max-w-3xl mx-auto">

            {/* Paper filter tags row */}
            {selectedPapers.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {selectedPapers.map((title) => (
                  <span
                    key={title}
                    className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-primary/10 text-primary text-[11px] font-medium max-w-[200px]"
                  >
                    <FileText className="w-3 h-3 shrink-0" />
                    <span className="truncate">{title}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedPapers((prev) => prev.filter((t) => t !== title))}
                      className="w-4 h-4 rounded-full flex items-center justify-center hover:bg-primary/20 transition-colors shrink-0"
                      aria-label={`Remove ${title}`}
                    >
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
                <button
                  type="button"
                  onClick={() => setSelectedPapers([])}
                  className="text-[11px] text-muted-foreground hover:text-foreground transition-colors px-1"
                >
                  Clear all
                </button>
              </div>
            )}

            {/* Textarea + buttons row */}
            <form onSubmit={handleSubmit} className="relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedPapers.length > 0
                    ? `Ask about ${selectedPapers.length} selected paper${selectedPapers.length > 1 ? "s" : ""}...`
                    : "Ask about your papers..."
                }
                rows={1}
                className="w-full resize-none rounded-[16px] border border-border bg-secondary/50 px-4 py-3 pl-11 pr-12 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/30 transition-all"
                style={{ minHeight: "48px", maxHeight: "200px" }}
              />

              {/* Scope picker toggle — vertically centred on the left */}
              <button
                ref={pickerBtnRef}
                type="button"
                onClick={() => {
                  setPickerOpen((o) => !o);
                  setPickerSearch("");
                }}
                className={cn(
                  "absolute left-2 top-[11px] w-7 h-7 rounded-[8px] flex items-center justify-center transition-all",
                  pickerOpen || selectedPapers.length > 0
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-secondary text-muted-foreground hover:text-foreground"
                )}
                title="Filter by papers"
                aria-label="Select papers to search"
              >
                <BookOpen className="w-3.5 h-3.5" />
              </button>

              {/* Picker popover — anchored to the bottom of the textarea container */}
              {pickerOpen && (
                <div
                  ref={pickerRef}
                  className="absolute bottom-full left-0 mb-2 w-72 bg-white rounded-[14px] border border-border shadow-lg overflow-hidden z-20"
                >
                  {/* Popover header */}
                  <div className="px-3 pt-3 pb-2 border-b border-border">
                    <p className="text-[11px] font-medium text-foreground mb-2">
                      Limit search to specific papers
                    </p>
                    <input
                      type="text"
                      value={pickerSearch}
                      onChange={(e) => setPickerSearch(e.target.value)}
                      placeholder="Filter papers..."
                      autoFocus
                      className="w-full h-7 px-2.5 rounded-[8px] border border-border text-[12px] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
                    />
                  </div>

                  {/* Paper list */}
                  <ul className="max-h-52 overflow-auto py-1">
                    {allPapers
                      .filter((p) =>
                        pickerSearch
                          ? p.title.toLowerCase().includes(pickerSearch.toLowerCase())
                          : true
                      )
                      .map((paper) => {
                        const isSelected = selectedPapers.includes(paper.title);
                        return (
                          <li
                            key={paper.title}
                            onClick={() => {
                              setSelectedPapers((prev) =>
                                isSelected
                                  ? prev.filter((t) => t !== paper.title)
                                  : [...prev, paper.title]
                              );
                            }}
                            className={cn(
                              "flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors",
                              isSelected
                                ? "bg-primary/10 hover:bg-primary/15"
                                : "hover:bg-secondary"
                            )}
                          >
                            {/* Checkbox */}
                            <div
                              className={cn(
                                "w-4 h-4 rounded-[4px] border-2 flex items-center justify-center shrink-0 transition-all",
                                isSelected ? "bg-primary border-primary" : "border-border"
                              )}
                            >
                              {isSelected && (
                                <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 10 10">
                                  <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-[12px] text-foreground truncate font-medium leading-tight">
                                {paper.title}
                              </p>
                              {paper.authors && paper.authors !== "unknown" && (
                                <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                                  {paper.authors}
                                </p>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    {allPapers.length === 0 && (
                      <li className="px-3 py-4 text-[12px] text-muted-foreground text-center">
                        No papers uploaded yet
                      </li>
                    )}
                  </ul>

                  {/* Footer */}
                  {selectedPapers.length > 0 && (
                    <div className="px-3 py-2 border-t border-border flex items-center justify-between">
                      <span className="text-[11px] text-primary font-medium">
                        {selectedPapers.length} selected
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedPapers([])}
                        className="text-[11px] text-muted-foreground hover:text-destructive transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Send button — vertically centred on the right */}
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className={cn(
                  "absolute right-3 top-[11px] w-8 h-8 rounded-[10px] flex items-center justify-center transition-all duration-150",
                  input.trim() && !isLoading
                    ? "bg-primary text-white hover:bg-primary/90"
                    : "bg-muted text-muted-foreground cursor-not-allowed"
                )}
                aria-label="Send message"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>

            <p className="text-center text-[11px] text-muted-foreground mt-2">
              {selectedPapers.length > 0
                ? `Searching ${selectedPapers.length} paper${selectedPapers.length > 1 ? "s" : ""} · click 📖 to change`
                : "PaperMind uses RAG to answer based on your uploaded papers."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Helpers ---

/**
 * 预处理 LaTeX 定界符：
 * 将 \( ... \) 转为 $...$（行内公式）
 * 将 \[ ... \] 转为 $$...$$（块级公式）
 * 这样 remark-math 能统一识别。
 */
function preprocessLaTeX(content: string): string {
  // 块级公式：\[ ... \] → $$ ... $$
  let processed = content.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => `$$${math}$$`);
  // 行内公式：\( ... \) → $ ... $
  processed = processed.replace(/\\\((.*?)\\\)/g, (_, math) => `$${math}$`);
  return processed;
}

// --- Sub-components ---

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="text-center max-w-md"
      >
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Sparkles className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-xl font-semibold text-foreground mb-2">
          Ask about your research
        </h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Ask questions about your uploaded papers. PaperMind retrieves relevant
          passages and generates answers with citations.
        </p>

        <div className="mt-8 grid gap-2">
          {[
            "What is the main contribution of this paper?",
            "Explain the methodology used",
            "How does this compare to previous work?",
          ].map((suggestion) => (
            <button
              key={suggestion}
              className="text-left px-4 py-3 rounded-[12px] border border-border text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

function ChatBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex items-start gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
          isUser ? "bg-foreground" : "bg-primary/10"
        )}
      >
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Brain className="w-4 h-4 text-primary" />
        )}
      </div>

      <div className={cn("flex-1 max-w-[85%]", isUser && "flex flex-col items-end")}>
        <div
          className={cn(
            "rounded-[16px] px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-foreground text-white"
              : "bg-secondary text-foreground"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {preprocessLaTeX(message.content)}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            <p className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
              Sources
            </p>
            {message.sources.map((source, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-3 py-1.5 rounded-[8px] bg-primary/5 border border-primary/10"
              >
                <FileText className="w-3 h-3 text-primary shrink-0" />
                <span className="text-[12px] text-foreground truncate">
                  {source.title}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  #{source.chunk_index}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
