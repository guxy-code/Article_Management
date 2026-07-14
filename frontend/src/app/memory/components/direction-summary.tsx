"use client";

import type { GraphSummaryField } from "@/lib/api";

interface Props {
  summary: GraphSummaryField[];
}

export default function DirectionSummary({ summary }: Props) {
  if (!summary || summary.length === 0) {
    return (
      <p className="text-[13px] text-muted-foreground py-4 text-center">
        图谱数据积累后将自动生成研究方向摘要
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {summary.map((field) => (
        <div key={field.name}>
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="w-2 h-2 rounded-full bg-purple-500" />
            <span className="text-[13px] font-medium">{field.name}</span>
          </div>
          {field.children.length > 0 && (
            <div className="ml-4 space-y-1.5">
              {field.children.map((topic) => (
                <div key={topic.name}>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                    <span className="text-[12px] text-foreground">{topic.name}</span>
                  </div>
                  {topic.children.length > 0 && (
                    <div className="ml-4 mt-0.5 space-y-0.5">
                      {topic.children.slice(0, 5).map((entity) => (
                        <div key={entity.name} className="flex items-baseline gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-emerald-400 shrink-0 mt-1.5" />
                          <span className="text-[11px] text-muted-foreground">
                            {entity.name}
                            {entity.description && ` — ${entity.description}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
