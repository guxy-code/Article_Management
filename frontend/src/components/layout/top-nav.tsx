"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, FileText, X, Loader2, LogOut, Settings, ChevronDown } from "lucide-react";
import { search } from "@/lib/api";
import { getUser, logout } from "@/lib/auth";

interface PaperResult {
  title: string;
  authors: string;
}

export function TopNav() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PaperResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [username, setUsername] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 获取当前用户名
  useEffect(() => {
    const user = getUser();
    setUsername(user?.username || "");
  }, []);

  // Close menu on outside click
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [menuOpen]);

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    const handleGlobalKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
    };
    window.addEventListener("keydown", handleGlobalKey);
    return () => window.removeEventListener("keydown", handleGlobalKey);
  }, []);

  // Close panel on outside click
  useEffect(() => {
    const handleOutside = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        !inputRef.current?.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [isOpen]);

  // Debounced search
  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); setIsLoading(false); return; }
    setIsLoading(true);
    try {
      const data = await search(q, 8);
      const seen = new Set<string>();
      const deduped: PaperResult[] = [];
      for (const r of data.results) {
        if (!seen.has(r.title)) {
          seen.add(r.title);
          deduped.push({ title: r.title, authors: r.authors });
        }
      }
      setResults(deduped);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setActiveIndex(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!val.trim()) { setResults([]); setIsLoading(false); return; }
    setIsLoading(true);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  };

  const handleClear = () => {
    setQuery(""); setResults([]); setIsOpen(false);
    inputRef.current?.blur();
  };

  const handleSelect = (title: string) => {
    router.push(`/library?paper=${encodeURIComponent(title)}`);
    handleClear();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen || results.length === 0) { if (e.key === "Escape") handleClear(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, -1)); }
    else if (e.key === "Enter") { e.preventDefault(); if (activeIndex >= 0 && results[activeIndex]) handleSelect(results[activeIndex].title); }
    else if (e.key === "Escape") handleClear();
  };

  const showPanel = isOpen && query.trim().length > 0;

  return (
    <header className="h-14 border-b border-border bg-white flex items-center justify-between px-6 relative z-30">
      {/* Search Bar */}
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search papers..."
          autoComplete="off"
          className="w-full h-9 pl-9 pr-16 rounded-[10px] bg-secondary border-none text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
        />
        {query ? (
          <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors" aria-label="Clear search">
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground bg-white px-1.5 py-0.5 rounded border border-border pointer-events-none">⌘K</kbd>
        )}

        {/* Results panel */}
        {showPanel && (
          <div ref={panelRef} className="absolute top-full left-0 mt-2 w-full bg-white rounded-[14px] border border-border shadow-lg overflow-hidden">
            {isLoading ? (
              <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />Searching...
              </div>
            ) : results.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted-foreground">No papers found for &ldquo;{query}&rdquo;</div>
            ) : (
              <ul role="listbox" className="py-1.5">
                {results.map((paper, i) => (
                  <li key={paper.title} role="option" aria-selected={activeIndex === i}
                    onMouseEnter={() => setActiveIndex(i)}
                    onClick={() => handleSelect(paper.title)}
                    className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors ${activeIndex === i ? "bg-primary/10 text-foreground" : "hover:bg-secondary"}`}
                  >
                    <div className={`w-7 h-7 rounded-[8px] flex items-center justify-center shrink-0 transition-colors ${activeIndex === i ? "bg-primary/10" : "bg-secondary"}`}>
                      <FileText className={`w-3.5 h-3.5 transition-colors ${activeIndex === i ? "text-primary" : "text-muted-foreground"}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[13px] font-medium text-foreground truncate leading-tight">{paper.title}</p>
                      {paper.authors && paper.authors !== "unknown" && (
                        <p className="text-[11px] text-muted-foreground truncate mt-0.5">{paper.authors}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {/* Right Section: user menu dropdown */}
      <div ref={menuRef} className="relative ml-4 shrink-0">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-2 px-2 py-1.5 rounded-[10px] hover:bg-secondary transition-colors"
        >
          <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center">
            <span className="text-xs font-semibold text-primary">
              {username ? username[0].toUpperCase() : "?"}
            </span>
          </div>
          {username && (
            <span className="text-[13px] text-muted-foreground hidden sm:block">{username}</span>
          )}
          <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform ${menuOpen ? "rotate-180" : ""}`} />
        </button>
        {menuOpen && (
          <div className="absolute top-full right-0 mt-2 w-44 bg-white rounded-[12px] border border-border shadow-lg overflow-hidden py-1">
            <button
              onClick={() => { router.push("/settings"); setMenuOpen(false); }}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-[13px] text-foreground hover:bg-secondary transition-colors"
            >
              <Settings className="w-4 h-4 text-muted-foreground" />
              Settings
            </button>
            <div className="h-px bg-border my-1" />
            <button
              onClick={logout}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-[13px] text-destructive hover:bg-destructive/5 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
