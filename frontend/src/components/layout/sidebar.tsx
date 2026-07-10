"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  MessageSquare,
  Library,
  BarChart3,
  Home,
  Brain,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "Workspace",
    items: [
      { href: "/", icon: Home, label: "Home" },
      { href: "/chat", icon: MessageSquare, label: "AI Chat" },
    ],
  },
  {
    title: "Research",
    items: [
      { href: "/library", icon: Library, label: "Library" },
      { href: "/discover", icon: Sparkles, label: "Discover" },
      { href: "/knowledge", icon: Brain, label: "Knowledge" },
    ],
  },
  {
    title: "Analytics",
    items: [
      { href: "/stats", icon: BarChart3, label: "Statistics" },
    ],
  },
];

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 64 : 240 }}
      transition={{ duration: 0.2, ease: "easeInOut" }}
      className="h-full border-r border-border bg-gradient-to-b from-white via-white to-indigo-50/30 flex flex-col relative z-20"
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-4 border-b border-border shrink-0">
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="flex items-center gap-2.5"
          >
            <div className="w-8 h-8 rounded-[10px] bg-primary flex items-center justify-center shadow-sm shadow-primary/20">
              <Brain className="w-[18px] h-[18px] text-white" />
            </div>
            <span className="font-semibold text-[15px] tracking-tight">
              PaperMind
            </span>
          </motion.div>
        )}
        {collapsed && (
          <div className="w-8 h-8 rounded-[10px] bg-primary flex items-center justify-center mx-auto shadow-sm shadow-primary/20">
            <Brain className="w-[18px] h-[18px] text-white" />
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 overflow-y-auto">
        {navSections.map((section, si) => (
          <div key={section.title} className={cn(si > 0 && "mt-4")}>
            {!collapsed && (
              <p className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider px-3 mb-1.5">
                {section.title}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group relative flex items-center gap-3 px-3 py-2 rounded-[10px] text-sm font-medium transition-all duration-150",
                      isActive
                        ? "bg-primary/10 text-primary font-semibold"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                  >
                    {/* Active indicator bar */}
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full bg-primary" />
                    )}
                    <item.icon className={cn(
                      "w-[18px] h-[18px] shrink-0 transition-colors",
                      isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                    )} />
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.05 }}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse Toggle */}
      <div className="p-2 border-t border-border shrink-0">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-[10px] text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? (
            <PanelLeftOpen className="w-[18px] h-[18px]" />
          ) : (
            <PanelLeftClose className="w-[18px] h-[18px]" />
          )}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </motion.aside>
  );
}
