"use client";

import { useState } from "react";
import {
  Send, Bot, User, Wrench, FileText,
  ChevronDown, ChevronRight, Plus, Sparkles,
  CheckCircle2, XCircle, Clock,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockChatSessions, mockChatMessages, mockEvidences } from "@/lib/mock-data";

type ToolTrace = NonNullable<(typeof mockChatMessages)[0]["tool_traces"]>[0];

function ToolTraceItem({ trace }: { trace: ToolTrace }) {
  const isOk = trace.status === "success";
  return (
    <div className="flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 font-mono text-[11px]">
      <Wrench className="h-3 w-3 text-slate-400 shrink-0" />
      <span className="text-blue-400 font-semibold">{trace.tool_name}</span>
      <span className="text-slate-500">→</span>
      <span className="text-slate-300 flex-1 truncate">{trace.output_summary}</span>
      <span className="text-slate-500 shrink-0">{trace.duration_ms}ms</span>
      {isOk
        ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
        : <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
      }
    </div>
  );
}

export default function ChatPage() {
  const [activeSession, setActiveSession] = useState(mockChatSessions[0].id);
  const [input, setInput] = useState("");
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set(["msg-1"]));

  const messages = mockChatMessages.filter((m) => m.session_id === activeSession);

  const toggleTrace = (id: string) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const relatedEvidence = mockEvidences.filter((e) =>
    messages.some((m) => m.evidence_refs?.includes(e.evidence_id))
  );

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-3">
      {/* ── Session List ────────────────────── */}
      <div className="w-56 shrink-0 flex flex-col gap-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">会话列表</span>
          <Button variant="ghost" size="icon">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {mockChatSessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSession(s.id)}
              className={cn(
                "w-full text-left rounded-lg px-3 py-2.5 text-sm transition-all duration-150",
                activeSession === s.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-50"
              )}
            >
              <p className="font-medium text-[13px] truncate">{s.title}</p>
              <p className={cn("text-[11px] mt-0.5 flex items-center gap-1", activeSession === s.id ? "text-blue-100" : "text-slate-400")}>
                <Clock className="h-2.5 w-2.5" />
                {formatDate(s.updated_at)}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* ── Chat Area ───────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-5 pb-4 pr-1">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn("flex gap-3 items-start", msg.role === "user" ? "justify-end" : "")}
            >
              {msg.role === "assistant" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700 shadow-sm mt-0.5">
                  <Sparkles className="h-3.5 w-3.5 text-white" />
                </div>
              )}

              <div
                className={cn(
                  "max-w-[72%] rounded-2xl text-sm",
                  msg.role === "user"
                    ? "bg-blue-600 text-white px-4 py-3 rounded-tr-sm shadow-sm"
                    : "bg-white border border-slate-200 px-4 py-3 rounded-tl-sm shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]"
                )}
              >
                {msg.agent_name && (
                  <p className={cn("text-[11px] font-medium mb-1.5 flex items-center gap-1", msg.role === "assistant" ? "text-blue-600" : "text-blue-200")}>
                    <Bot className="h-3 w-3" /> {msg.agent_name}
                  </p>
                )}
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                {/* Tool traces */}
                {msg.tool_traces && msg.tool_traces.length > 0 && (
                  <div className={cn("mt-3 pt-2", msg.role === "assistant" ? "border-t border-slate-100" : "border-t border-blue-500/30")}>
                    <button
                      onClick={() => toggleTrace(msg.id)}
                      className={cn(
                        "flex items-center gap-1.5 text-[11px] font-medium transition-colors",
                        msg.role === "assistant" ? "text-slate-500 hover:text-slate-700" : "text-blue-200 hover:text-white"
                      )}
                    >
                      {expandedTraces.has(msg.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      工具调用 ({msg.tool_traces.length})
                    </button>
                    {expandedTraces.has(msg.id) && (
                      <div className="mt-2 space-y-1.5">
                        {msg.tool_traces.map((t, i) => <ToolTraceItem key={i} trace={t} />)}
                      </div>
                    )}
                  </div>
                )}

                {/* Recommended actions */}
                {msg.recommended_actions && msg.recommended_actions.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-100">
                    <p className="text-[11px] text-slate-500 mb-1.5 font-medium">建议动作</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.recommended_actions.map((a, i) => (
                        <Badge key={i} variant="info" className="cursor-pointer hover:bg-sky-100 transition-colors">{a}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {msg.role === "user" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 mt-0.5">
                  <User className="h-3.5 w-3.5 text-slate-200" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Input bar */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入运维问题或指令，例如：分析 ESX-04 的 CPU 告警原因..."
              rows={2}
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700 placeholder:text-slate-400
                         focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
            <Button size="md" className="shrink-0 self-end">
              <Send className="h-4 w-4" />
              发送
            </Button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1.5 pl-0.5">支持自然语言，AI 将自动调用相关工具诊断</p>
        </div>
      </div>

      {/* ── Evidence Sidebar ─────────────────── */}
      <div className="w-64 shrink-0 overflow-y-auto space-y-3">
        <div className="px-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">关联证据</span>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] overflow-hidden">
          {relatedEvidence.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <FileText className="h-8 w-8 text-slate-200 mb-2" />
              <p className="text-xs text-slate-400">暂无关联证据</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {relatedEvidence.map((e) => (
                <div key={e.evidence_id} className="p-3 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between mb-1.5">
                    <Badge variant="neutral">{e.source_type}</Badge>
                    <div className="flex items-center gap-1">
                      <div className="h-1 w-14 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${e.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-[11px] text-slate-500">{(e.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">{e.summary}</p>
                  <p className="text-[11px] text-slate-400 mt-1">{formatDate(e.timestamp)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
