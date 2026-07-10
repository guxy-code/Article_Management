"use client";

import { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";
import { isAuthenticated } from "@/lib/auth";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // 登录页不需要验证
    if (pathname === "/login") {
      setChecked(true);
      return;
    }
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setChecked(true);
  }, [pathname, router]);

  // 登录页直接渲染（无 sidebar/topnav）
  if (pathname === "/login") {
    return <>{children}</>;
  }

  // 认证检查完成前不渲染，防止闪屏
  if (!checked) return null;

  return (
    <div className="h-screen flex overflow-hidden">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
