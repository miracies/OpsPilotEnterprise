"use client";

import { useState } from "react";
import { Send, Bot, User, Wrench, FileText, ChevronDown, ChevronRight, Plus } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { mockChatSessions, mockChatMessages, mockEvidences } from "@/lib/mock-data";

function ToolTraceItem({ trace }: { trace: (typeof mockChatMessages)[0]["tool_traces"] extends (infer T)[] | undefined ? T : never }) {
  if (!trace) return null;
  return (
    <div className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1.5 font-mono">
      <Wrench className="h-3 w-3 text-gray-400 shrink-0" />
      <span className="text-blue-700 font-medium">{trace.tool_name}</span>
      <span className="text-gray-400">→</span>
      <span className="text-gray-600 truncate">{trace.output_summary}</span>
      <span className="ml-auto text-gray-400 shrink-0">{trace.duration_ms}ms</span>
      <Badge variant={trace.status === "success" ? "success" : "danger"} className="text-[10px]">{trace.status}</Badge>
    </div>
  );
}

export default function ChatPage() {
  const [activeSession, setActiveSession] = useState(mockChatSessions[0].id);
  const [input, setInput] = useState("");
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
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
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Session list */}
      <div className="w-64 shrink-0 flex flex-col">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">会话</h2>
          <Button variant="ghost" size="sm"><Plus className="h-4 w-4" /></Button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {mockChatSessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSession(s.id)}
              className={cn(
                "w-full text-left rounded-md px-3 py-2 text-sm transition-colors",
                activeSession === s.id ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:bg-gray-50"
              )}
            >
              <p className="font-medium truncate">{s.title}</p>
              <p className="text-xs text-gray-400 mt-0.5">{formatDate(s.updated_at)}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        <div className="flex-1 overflow-y-auto space-y-4 pb-4">
          {messages.map((msg) => (
            <div key={msg.id} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "")}>
              {msg.role === "assistant" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-100">
                  <Bot className="h-4 w-4 text-blue-700" />
                </div>
              )}
              <div className={cn("max-w-[70%] rounded-lg p-4 text-sm", msg.role === "user" ? "bg-blue-600 text-white" : "bg-white border border-gray-200")}>
                {msg.agent_name && (
                  <p className="text-xs text-gray-400 mb-1">{msg.agent_name}</p>
                )}
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                {msg.tool_traces && msg.tool_traces.length > 0 && (
                  <div className="mt-3 border-t border-gray-100 pt-2">
                    <button onClick={() => toggleTrace(msg.id)} className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700">
                      {expandedTraces.has(msg.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      工具调用 ({msg.tool_traces.length})
                    </button>
                    {expandedTraces.has(msg.id) && (
                      <div className="mt-2 space-y-1">
                        {msg.tool_traces.map((t, i) => (
                          <ToolTraceItem key={i} trace={t} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {msg.recommended_actions && msg.recommended_actions.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {msg.recommended_actions.map((a, i) => (
                      <Badge key={i} variant="info">{a}</Badge>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200">
                  <User className="h-4 w-4 text-gray-600" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 bg-white rounded-lg p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="输入运维问题或指令..."
              rows={2}
              className="flex-1 resize-none rounded-md border border-gray-200 bg-gray-50 p-2 text-sm placeholder:text-gray-400 focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
            />
            <Button size="md"><Send className="h-4 w-4" /></Button>
          </div>
        </div>
      </div>

      {/* Context sidebar */}
      <div className="w-72 shrink-0 overflow-y-auto space-y-4">
        <Card>
          <CardContent>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">关联证据</h3>
            {relatedEvidence.length === 0 ? (
              <p className="text-xs text-gray-400">暂无</p>
            ) : (
              <div className="space-y-2">
                {relatedEvidence.map((e) => (
                  <div key={e.evidence_id} className="rounded border border-gray-100 p-2 text-xs">
                    <div className="flex items-center gap-1 mb-1">
                      <FileText className="h-3 w-3 text-gray-400" />
                      <Badge variant="neutral">{e.source_type}</Badge>
                      <span className="ml-auto text-gray-400">{(e.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-gray-700">{e.summary}</p>
                    <p className="text-gray-400 mt-0.5">{formatDate(e.timestamp)}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
