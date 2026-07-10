"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { X, Send, Loader2, Bot, User, Trash2 } from "lucide-react";
import { createSession, getSession, chatStream } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  quote?: string;
}

interface PdfChatPanelProps {
  paperTitle: string;
  pendingQuote: string | null;
  onClose: () => void;
  onQuoteConsumed: () => void;
}

/** localStorage key per paper */
function sessionKey(paperTitle: string) {
  return `papermind_pdf_session_${paperTitle}`;
}

export function PdfChatPanel({
  paperTitle,
  pendingQuote,
  onClose,
  onQuoteConsumed,
}: PdfChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [currentQuote, setCurrentQuote] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initRef = useRef(false); // guard against StrictMode double-invoke

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Initialize: reuse existing session for this paper or create a new one
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    async function init() {
      setIsLoadingHistory(true);
      try {
        const stored = localStorage.getItem(sessionKey(paperTitle));
        if (stored) {
          // Try to load existing session history
          try {
            const session = await getSession(stored);
            setSessionId(session.id);
            // Map backend messages to local format
            const loaded: Message[] = session.messages.map((m) => ({
              role: m.role,
              content: m.content,
            }));
            setMessages(loaded);
            return;
          } catch {
            // Session no longer exists on backend, create a fresh one
            localStorage.removeItem(sessionKey(paperTitle));
          }
        }
        // No stored session — create a new one
        const s = await createSession();
        localStorage.setItem(sessionKey(paperTitle), s.id);
        setSessionId(s.id);
      } catch (err) {
        console.error("Failed to initialize chat session:", err);
      } finally {
        setIsLoadingHistory(false);
      }
    }

    init();
  // paperTitle is stable for the lifetime of this panel instance
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When a new quote arrives, set it as the pending input context
  useEffect(() => {
    if (pendingQuote) {
      setCurrentQuote(pendingQuote);
      onQuoteConsumed();
      inputRef.current?.focus();
    }
  }, [pendingQuote, onQuoteConsumed]);

  const sendMessage = useCallback(async () => {
    const question = input.trim();
    if (!question || !sessionId || isStreaming) return;

    const quote = currentQuote;
    // Always include paper context so the backend knows which paper to focus on.
    // When the user selects a quote, prepend it; otherwise just ask about the paper directly.
    const fullQuestion = quote
      ? `关于论文《${paperTitle}》中的这段话：\n\n"${quote}"\n\n${question}`
      : question;

    const userMsg: Message = { role: "user", content: question, quote: quote ?? undefined };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setCurrentQuote(null);
    setIsStreaming(true);

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      await chatStream(
        sessionId,
        fullQuestion,
        {
          onSources: () => {},
          onToken: (token) => {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + token,
              };
              return updated;
            });
          },
          onDone: () => {
            setIsStreaming(false);
          },
          onError: (err) => {
            console.error("Chat error:", err);
            setIsStreaming(false);
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: "Sorry, something went wrong. Please try again.",
              };
              return updated;
            });
          },
        },
        5,
        paperTitle, // pass current paper title so backend restricts retrieval to this paper
      );
    } catch (err) {
      console.error(err);
      setIsStreaming(false);
    }
  }, [input, sessionId, isStreaming, currentQuote, paperTitle]);

  const clearChat = async () => {
    setMessages([]);
    setCurrentQuote(null);
    // Remove stored session and create a fresh one
    localStorage.removeItem(sessionKey(paperTitle));
    try {
      const s = await createSession();
      localStorage.setItem(sessionKey(paperTitle), s.id);
      setSessionId(s.id);
    } catch (err) {
      console.error("Failed to create new session:", err);
    }
  };

  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 320, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="h-full border-l border-border bg-white flex flex-col overflow-hidden shrink-0"
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-medium text-foreground">Ask AI</h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={clearChat}
            className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
            title="Clear chat"
            aria-label="Clear chat"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-[8px] flex items-center justify-center hover:bg-secondary text-muted-foreground hover:text-foreground transition-all"
            aria-label="Close panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-3 space-y-3">
        {isLoadingHistory ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <Bot className="w-8 h-8 text-muted-foreground/40 mb-2" />
            <p className="text-xs text-muted-foreground">Ask anything about this paper</p>
            <p className="text-[11px] text-muted-foreground mt-1">
              Select text and click <span className="font-medium">Ask AI</span> to ask about a specific passage
            </p>
          </div>
        ) : (
          messages.map((msg, i) => (
          <div key={i} className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}>
            {/* Quote block for user messages */}
            {msg.role === "user" && msg.quote && (
              <div className="max-w-[90%] px-2.5 py-1.5 rounded-[8px] bg-amber-50 border border-amber-200 text-[11px] text-amber-800 italic line-clamp-2">
                &ldquo;{msg.quote}&rdquo;
              </div>
            )}

            {/* Message bubble */}
            <div
              className={`max-w-[90%] px-3 py-2 rounded-[10px] text-xs leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-white"
                  : "bg-secondary text-foreground"
              }`}
            >
              {msg.content || (
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Thinking...
                </span>
              )}
            </div>

            {/* Role label */}
            <div className={`flex items-center gap-1 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              {msg.role === "user" ? (
                <User className="w-2.5 h-2.5 text-muted-foreground" />
              ) : (
                <Bot className="w-2.5 h-2.5 text-primary" />
              )}
              <span className="text-[10px] text-muted-foreground">
                {msg.role === "user" ? "You" : "AI"}
              </span>
            </div>
          </div>
        ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quote preview */}
      {currentQuote && (
        <div className="mx-3 mb-1 px-2.5 py-1.5 rounded-[8px] bg-amber-50 border border-amber-200 flex items-start gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] text-amber-600 font-medium mb-0.5">Asking about:</p>
            <p className="text-[11px] text-amber-800 italic line-clamp-2">&ldquo;{currentQuote}&rdquo;</p>
          </div>
          <button
            onClick={() => setCurrentQuote(null)}
            className="shrink-0 text-amber-500 hover:text-amber-700 transition-colors mt-0.5"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Input */}
      <div className="p-3 border-t border-border">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            placeholder={currentQuote ? "Ask about the selection..." : "Ask about this paper..."}
            disabled={isStreaming}
            className="flex-1 h-8 px-3 rounded-[8px] border border-border text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 transition-shadow disabled:opacity-50"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isStreaming}
            className="w-8 h-8 rounded-[8px] bg-primary text-white flex items-center justify-center disabled:opacity-30 hover:bg-primary/90 transition-colors shrink-0"
            aria-label="Send"
          >
            {isStreaming ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
