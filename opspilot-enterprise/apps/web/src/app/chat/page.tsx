"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Send, Bot, User, Wrench, FileText,
  ChevronDown, ChevronRight, Plus, Sparkles,
  CheckCircle2, XCircle, Clock, Loader2, ExternalLink,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import type { ChatSession, ChatMessage, ToolTrace } from "@opspilot/shared-types";

interface Evidence {
  evidence_id: string;
  source_type: string;
  summary: string;
  confidence: number;
  timestamp: string;
}

function ToolTraceItem({ trace }: { trace: ToolTrace }) {
  const isOk = trace.status === "success";
  return (
    <div className="flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 font-mono text-[11px]">
      <Wrench className="h-3 w-3 text-slate-400 shrink-0" />
      <span className="text-blue-400 font-semibold">{trace.tool_name}</span>
      <span className="text-slate-500">&rarr;</span>
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
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [expandedTraces, setExpandedTraces] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Load sessions on mount
  useEffect(() => {
    apiFetch<{ data: ChatSession[] }>("/api/v1/chat/sessions")
      .then((res) => {
        setSessions(res.data ?? []);
      })
      .catch(() => {});
  }, []);

  // Load messages & evidence when active session changes
  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      setEvidence([]);
      return;
    }
    apiFetch<{ data: ChatMessage[] }>(`/api/v1/chat/sessions/${activeSession}/messages`)
      .then((res) => setMessages(res.data ?? []))
      .catch(() => setMessages([]));

    apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${activeSession}/evidence`)
      .then((res) => setEvidence(res.data ?? []))
      .catch(() => setEvidence([]));
  }, [activeSession]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  async function createSession() {
    try {
      const res = await apiFetch<{ data: ChatSession }>("/api/v1/chat/sessions", {
        method: "POST",
        body: JSON.stringify({ title: null }),
      });
      const newSession = res.data;
      setSessions((prev) => [newSession, ...prev]);
      setActiveSession(newSession.id);
    } catch {}
  }

  async function handleSend() {
    if (!input.trim() || sending) return;

    let sid = activeSession;
    if (!sid) {
      try {
        const res = await apiFetch<{ data: ChatSession }>("/api/v1/chat/sessions", {
          method: "POST",
          body: JSON.stringify({ title: input.trim().slice(0, 30) }),
        });
        sid = res.data.id;
        setSessions((prev) => [res.data, ...prev]);
        setActiveSession(sid);
      } catch {
        return;
      }
    }

    const userMsg: ChatMessage = {
      id: `tmp-${Date.now()}`,
      session_id: sid,
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const res = await apiFetch<{ data: ChatMessage }>(`/api/v1/chat/sessions/${sid}/messages`, {
        method: "POST",
        body: JSON.stringify({ message: userMsg.content }),
      });
      const assistantMsg = res.data;
      setMessages((prev) => [...prev, assistantMsg]);

      if (assistantMsg.tool_traces && assistantMsg.tool_traces.length > 0) {
        setExpandedTraces((prev) => new Set([...prev, assistantMsg.id]));
      }

      // Refresh evidence
      const evRes = await apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${sid}/evidence`);
      setEvidence(evRes.data ?? []);

      // Update session list title
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid ? { ...s, title: userMsg.content.slice(0, 30), updated_at: new Date().toISOString(), message_count: s.message_count + 2 } : s
        )
      );
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          session_id: sid!,
          role: "assistant",
          content: "抱歉，消息发送失败，请稍后重试。",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const toggleTrace = (id: string) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-3">
      {/* Session List */}
      <div className="w-56 shrink-0 flex flex-col gap-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">会话列表</span>
          <Button variant="ghost" size="icon" onClick={createSession}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto space-y-1 rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {sessions.length === 0 && (
            <div className="flex flex-col items-center py-10 text-center">
              <p className="text-xs text-slate-400">暂无会话</p>
              <p className="text-[11px] text-slate-300 mt-1">点击 + 创建新会话</p>
            </div>
          )}
          {sessions.map((s) => (
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

      {/* Chat Area */}
      <div className="flex flex-1 flex-col min-w-0">
        <div className="flex-1 overflow-y-auto space-y-5 pb-4 pr-1">
          {messages.length === 0 && !sending && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Sparkles className="h-10 w-10 text-blue-200 mb-3" />
              <p className="text-sm text-slate-500 font-medium">开始新的运维对话</p>
              <p className="text-xs text-slate-400 mt-1">输入运维问题或指令，AI 将自动调用工具诊断</p>
            </div>
          )}
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

                {/* Diagnosis CTA */}
                {msg.diagnosis_id && (
                  <div className="mt-3 pt-2 border-t border-slate-100">
                    <a
                      href={`/diagnosis?diagnosis_id=${msg.diagnosis_id}`}
                      className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 hover:text-blue-800 transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                      查看诊断详情
                    </a>
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
          {sending && (
            <div className="flex gap-3 items-start">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700 shadow-sm">
                <Sparkles className="h-3.5 w-3.5 text-white" />
              </div>
              <div className="bg-white border border-slate-200 px-4 py-3 rounded-2xl rounded-tl-sm shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在分析中...
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入运维问题或指令，例如：分析 ESX-04 的 CPU 告警原因..."
              rows={2}
              disabled={sending}
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700 placeholder:text-slate-400
                         focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all
                         disabled:opacity-60"
            />
            <Button size="md" className="shrink-0 self-end" onClick={handleSend} disabled={sending || !input.trim()}>
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              发送
            </Button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1.5 pl-0.5">支持自然语言，AI 将自动调用相关工具诊断 · Enter 发送，Shift+Enter 换行</p>
        </div>
      </div>

      {/* Evidence Sidebar */}
      <div className="w-64 shrink-0 overflow-y-auto space-y-3">
        <div className="px-1">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">关联证据</span>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] overflow-hidden">
          {evidence.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <FileText className="h-8 w-8 text-slate-200 mb-2" />
              <p className="text-xs text-slate-400">暂无关联证据</p>
              <p className="text-[11px] text-slate-300 mt-0.5">发送诊断请求后将显示证据</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {evidence.map((e) => (
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
