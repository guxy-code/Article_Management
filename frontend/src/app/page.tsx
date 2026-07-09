"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  MessageSquare,
  Library,
  Brain,
  ArrowRight,
  FileText,
  Plus,
  Check,
  Trash2,
} from "lucide-react";
import {
  getGraphStats,
  getConceptFrequency,
  getPapersWithConcepts,
  getUploadHistory,
  type ConceptFrequency,
  type PaperWithConcepts,
  type UploadDay,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// --- Todo ---
interface TodoItem { id: string; text: string; done: boolean; }
const TODO_KEY = "papermind_todos";
function loadTodos(): TodoItem[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(TODO_KEY) || "[]"); } catch { return []; }
}
function saveTodos(todos: TodoItem[]) { localStorage.setItem(TODO_KEY, JSON.stringify(todos)); }

export default function HomePage() {
  const [stats, setStats] = useState<Record<string, any>>({});
  const [concepts, setConcepts] = useState<ConceptFrequency[]>([]);
  const [papers, setPapers] = useState<PaperWithConcepts[]>([]);
  const [uploadDays, setUploadDays] = useState<UploadDay[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [newTodo, setNewTodo] = useState("");

  useEffect(() => {
    Promise.all([
      getGraphStats().catch(() => ({})),
      getConceptFrequency().catch(() => ({ concepts: [] })),
      getPapersWithConcepts().catch(() => ({ papers: [] })),
      getUploadHistory().catch(() => ({ days: [] })),
    ]).then(([s, c, p, uh]) => {
      setStats(s);
      setConcepts(c.concepts);
      setPapers(p.papers);
      setUploadDays(uh.days);
    });
    setTodos(loadTodos());
  }, []);

  const addTodo = () => {
    if (!newTodo.trim()) return;
    const updated = [...todos, { id: crypto.randomUUID(), text: newTodo.trim(), done: false }];
    setTodos(updated); saveTodos(updated); setNewTodo("");
  };
  const toggleTodo = (id: string) => {
    const updated = todos.map((t) => (t.id === id ? { ...t, done: !t.done } : t));
    setTodos(updated); saveTodos(updated);
  };
  const deleteTodo = (id: string) => {
    const updated = todos.filter((t) => t.id !== id);
    setTodos(updated); saveTodos(updated);
  };

  const nodeCount = stats.nodes || {};
  const paperCount = nodeCount.Paper || 0;
  const methodCount = nodeCount.Method || 0;
  const conceptCount = nodeCount.Concept || 0;
  const totalRelations = stats.total_edges || 0;

  return (
    <div className="h-full overflow-auto">
      <div className="px-6 py-5">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>

          {/* Header */}
          <h1 className="text-lg font-semibold tracking-tight mb-4">Research Dashboard</h1>

          {/* Stat Cards */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            <motion.div whileHover={{ y: -2 }} className="p-4 rounded-[14px] bg-indigo-50 cursor-default">
              <FileText className="w-5 h-5 text-indigo-600 mb-2" />
              <p className="text-2xl font-bold">{paperCount}</p>
              <p className="text-[12px] text-muted-foreground">Papers</p>
            </motion.div>
            <motion.div whileHover={{ y: -2 }} className="p-4 rounded-[14px] bg-blue-50 cursor-default">
              <svg className="w-5 h-5 text-blue-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
              <p className="text-2xl font-bold">{methodCount}</p>
              <p className="text-[12px] text-muted-foreground">Methods</p>
            </motion.div>
            <motion.div whileHover={{ y: -2 }} className="p-4 rounded-[14px] bg-purple-50 cursor-default">
              <svg className="w-5 h-5 text-purple-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" /></svg>
              <p className="text-2xl font-bold">{conceptCount}</p>
              <p className="text-[12px] text-muted-foreground">Topics</p>
            </motion.div>
            <motion.div whileHover={{ y: -2 }} className="p-4 rounded-[14px] bg-emerald-50 cursor-default">
              <svg className="w-5 h-5 text-emerald-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
              <p className="text-2xl font-bold">{totalRelations}</p>
              <p className="text-[12px] text-muted-foreground">Relations</p>
            </motion.div>
          </div>

          {/* Row 1: Research Focus + Upload Activity */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Research Focus */}
            <div className="p-4 rounded-[14px] border border-border bg-white">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium">Research Focus</h2>
                <Link href="/stats" className="text-[11px] text-primary hover:underline">Details →</Link>
              </div>
              {concepts.length > 0 ? (
                <div className="space-y-2.5">
                  {concepts.slice(0, 5).map((c) => {
                    const max = concepts[0]?.count || 1;
                    const pct = (c.count / max) * 100;
                    return (
                      <div key={c.name} className="flex items-center gap-2 group">
                        <span className="text-[12px] text-foreground w-36 truncate shrink-0 group-hover:text-primary transition-colors">{c.name}</span>
                        <div className="flex-1 h-5 bg-secondary rounded-[6px] overflow-hidden">
                          <motion.div
                            className="h-full bg-primary/20 rounded-[6px] group-hover:bg-primary/40 transition-colors"
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.max(pct, 12)}%` }}
                            transition={{ duration: 0.5, delay: 0.1 }}
                          />
                        </div>
                        <span className="text-[11px] text-muted-foreground w-5 text-right group-hover:text-primary transition-colors">{c.count}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">Upload papers to see focus areas</p>
              )}
            </div>

            {/* Upload Activity */}
            <div className="p-4 rounded-[14px] border border-border bg-white">
              <h2 className="text-sm font-medium mb-3">Upload Activity</h2>
              <div className="flex items-end gap-3 h-28">
                {uploadDays.map((day) => {
                  const maxCount = Math.max(...uploadDays.map(d => d.count), 1);
                  const height = day.count > 0 ? Math.max((day.count / maxCount) * 100, 10) : 5;
                  return (
                    <div key={day.date} className="flex-1 flex flex-col items-center gap-1.5 group">
                      <span className={`text-[10px] font-medium transition-all ${day.count > 0 ? "text-primary" : "text-transparent group-hover:text-muted-foreground"}`}>
                        {day.count}
                      </span>
                      <div className="w-full flex-1 flex items-end">
                        <div
                          className={`w-full rounded-t-[5px] transition-all duration-300 ${day.count > 0 ? "bg-primary/50 group-hover:bg-primary" : "bg-secondary group-hover:bg-secondary"}`}
                          style={{ height: `${height}%` }}
                        />
                      </div>
                      <span className="text-[9px] text-muted-foreground">{day.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Row 2: Recent Papers + To-Do */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Recent Papers */}
            <div className="p-4 rounded-[14px] border border-border bg-white">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium">Recent Papers</h2>
                <Link href="/library" className="text-[11px] text-primary hover:underline">All →</Link>
              </div>
              {papers.length > 0 ? (
                <div className="space-y-2">
                  {papers.slice(0, 5).map((p) => (
                    <Link key={p.title} href={`/knowledge?paper=${encodeURIComponent(p.title)}`} className="flex items-center gap-2.5 px-2.5 py-2 rounded-[8px] hover:bg-secondary/50 transition-colors group">
                      <FileText className="w-4 h-4 text-primary/60 group-hover:text-primary shrink-0 transition-colors" />
                      <span className="text-[12px] text-foreground truncate flex-1">{p.title}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0">{p.concepts.length} topics</span>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">No papers yet</p>
              )}
            </div>

            {/* To-Do */}
            <div className="p-4 rounded-[14px] border border-border bg-white">
              <h2 className="text-sm font-medium mb-3">To-Do</h2>
              <div className="space-y-2 mb-3 max-h-[160px] overflow-auto pr-0.5">
                {todos.map((todo) => (
                  <div key={todo.id} className="group flex items-center gap-2.5 px-2.5 py-2 rounded-[8px] hover:bg-secondary/50 transition-colors">
                    <button onClick={() => toggleTodo(todo.id)} className={cn("w-4.5 h-4.5 rounded-[5px] border-2 flex items-center justify-center shrink-0 transition-all", todo.done ? "bg-primary border-primary" : "border-border hover:border-primary/50")}>
                      {todo.done && <Check className="w-3 h-3 text-white" />}
                    </button>
                    <span className={cn("text-sm flex-1 truncate", todo.done && "line-through text-muted-foreground")}>{todo.text}</span>
                    <button onClick={() => deleteTodo(todo.id)} className="w-5 h-5 flex items-center justify-center opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {todos.length === 0 && <p className="text-sm text-muted-foreground py-3 text-center">No tasks yet</p>}
              </div>
              <div className="flex gap-2">
                <input value={newTodo} onChange={(e) => setNewTodo(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addTodo()} placeholder="Add a task..." className="flex-1 h-9 px-3 rounded-[8px] border border-border text-[12px] placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow" />
                <button onClick={addTodo} disabled={!newTodo.trim()} className="w-9 h-9 rounded-[8px] bg-primary text-white flex items-center justify-center disabled:opacity-30 hover:bg-primary/90 transition-colors">
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Row 3: Quick Actions */}
          <div className="grid grid-cols-3 gap-3">
            <Link href="/chat" className="group flex items-center gap-2.5 px-4 py-3.5 rounded-[12px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all">
              <MessageSquare className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
              <span className="text-[13px] font-medium">Ask AI</span>
              <ArrowRight className="w-4 h-4 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
            <Link href="/library" className="group flex items-center gap-2.5 px-4 py-3.5 rounded-[12px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all">
              <Library className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
              <span className="text-[13px] font-medium">Library</span>
              <ArrowRight className="w-4 h-4 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
            <Link href="/knowledge" className="group flex items-center gap-2.5 px-4 py-3.5 rounded-[12px] border border-border bg-white hover:border-primary/20 hover:shadow-sm transition-all">
              <Brain className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
              <span className="text-[13px] font-medium">Knowledge</span>
              <ArrowRight className="w-4 h-4 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
          </div>

        </motion.div>
      </div>
    </div>
  );
}
