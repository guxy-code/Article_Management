"use client";

import { Search } from "lucide-react";

export function TopNav() {
  return (
    <header className="h-14 border-b border-border bg-white flex items-center justify-between px-6">
      {/* Search Bar */}
      <div className="relative w-full max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search papers, ask questions..."
          className="w-full h-9 pl-9 pr-4 rounded-[10px] bg-secondary border-none text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
        />
        <kbd className="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground bg-white px-1.5 py-0.5 rounded border border-border">
          ⌘K
        </kbd>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="text-xs font-medium text-primary">R</span>
        </div>
      </div>
    </header>
  );
}
