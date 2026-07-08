"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { MessageSquare, Library, Upload, Brain, ArrowRight } from "lucide-react";

export default function HomePage() {
  return (
    <div className="h-full flex flex-col items-center justify-center px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="text-center max-w-lg"
      >
        {/* Hero */}
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
          <Brain className="w-8 h-8 text-primary" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight mb-2">
          Welcome to PaperMind
        </h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Your AI research workspace. Upload papers, ask questions, and build
          your knowledge graph.
        </p>

        {/* Quick Actions */}
        <div className="mt-10 grid gap-3">
          <QuickAction
            href="/chat"
            icon={MessageSquare}
            title="Ask AI"
            description="Chat with your paper knowledge base"
          />
          <QuickAction
            href="/library"
            icon={Library}
            title="Library"
            description="Browse and manage your papers"
          />
          <QuickAction
            href="/library"
            icon={Upload}
            title="Upload Paper"
            description="Add a new PDF to your knowledge base"
          />
        </div>
      </motion.div>
    </div>
  );
}

function QuickAction({
  href,
  icon: Icon,
  title,
  description,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-4 px-4 py-3 rounded-[16px] border border-border bg-white hover:border-primary/30 hover:shadow-sm transition-all duration-200"
    >
      <div className="w-10 h-10 rounded-[12px] bg-secondary flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
        <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
      <div className="flex-1 text-left">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-[12px] text-muted-foreground">{description}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </Link>
  );
}
