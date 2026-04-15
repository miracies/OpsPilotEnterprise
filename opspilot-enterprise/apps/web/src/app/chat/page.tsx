"use client";

import { useState, useEffect, useRef, useCallback, type ComponentType } from "react";
import {
  Send,
  Bot,
  User,
  Wrench,
  FileText,
  ChevronDown,
  ChevronRight,
  Plus,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ExternalLink,
  Brain,
  CircleDashed,
  Play,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import type { ChatSession, ChatMessage, ToolTrace } from "@opspilot/shared-types";
import Link from "next/link";

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
      {isOk ? (
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
      ) : (
        <XCircle className="h-3.5 w-3.5 text-red-400 shrink-0" />
      )}
    </div>
  );
}

function ProgressStatusItem({
  event,
}: {
  event: NonNullable<ChatMessage["progress_events"]>[number];
}) {
  const stageMeta: Record<
    NonNullable<ChatMessage["progress_events"]>[number]["stage"],
    {
      label: string;
      icon: ComponentType<{ className?: string }>;
      color: string;
      badgeBg: string;
    }
  > = {
    received: {
      label: "已接收请求",
      icon: CircleDashed,
      color: "text-slate-600",
      badgeBg: "bg-slate-100",
    },
    intent_parsed: {
      label: "意图识别中",
      icon: Brain,
      color: "text-violet-600",
      badgeBg: "bg-violet-100",
    },
    agent_selected: {
      label: "Agent 选择中",
      icon: Bot,
      color: "text-indigo-600",
      badgeBg: "bg-indigo-100",
    },
    tool_invoking: {
      label: "调用资源中",
      icon: Wrench,
      color: "text-blue-600",
      badgeBg: "bg-blue-100",
    },
    tool_done: {
      label: "资源调用完成",
      icon: CheckCircle2,
      color: "text-emerald-600",
      badgeBg: "bg-emerald-100",
    },
    tool_error: {
      label: "资源调用失败",
      icon: XCircle,
      color: "text-red-600",
      badgeBg: "bg-red-100",
    },
    completed: {
      label: "汇总结果中",
      icon: CheckCircle2,
      color: "text-emerald-700",
      badgeBg: "bg-emerald-100",
    },
    failed: {
      label: "任务失败",
      icon: XCircle,
      color: "text-red-700",
      badgeBg: "bg-red-100",
    },
  };

  const meta = stageMeta[event.stage];
  const StatusIcon = meta.icon;
  const statusText =
    event.status === "error" ? "失败" : event.status === "success" ? "完成" : "进行中";

  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5", meta.badgeBg)}>
        <StatusIcon className={cn("h-3.5 w-3.5 shrink-0", meta.color)} />
        <span className={cn("font-medium", meta.color)}>{meta.label}</span>
      </span>
      <span className="text-slate-500">{statusText}</span>
      <span className="text-slate-600 truncate">{event.text}</span>
      <span className="text-slate-400 shrink-0">{formatDate(event.ts)}</span>
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
  const executionHref = activeSession ? `/executions?session_id=${activeSession}` : "/executions";

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    apiFetch<{ data: ChatSession[] }>("/api/v1/chat/sessions")
      .then((res) => {
        setSessions(res.data ?? []);
      })
      .catch(() => {});
  }, []);

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

  useEffect(() => {
    if (!activeSession) return;
    const hasInProgress = messages.some((m) => m.status === "in_progress");
    if (!hasInProgress) return;

    const timer = setInterval(() => {
      apiFetch<{ data: ChatMessage[] }>(`/api/v1/chat/sessions/${activeSession}/messages`)
        .then((res) => setMessages(res.data ?? []))
        .catch(() => {});
    }, 1500);

    return () => clearInterval(timer);
  }, [activeSession, messages]);

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

      const evRes = await apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${sid}/evidence`);
      setEvidence(evRes.data ?? []);

      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid
            ? {
                ...s,
                title: userMsg.content.slice(0, 30),
                updated_at: new Date().toISOString(),
                message_count: s.message_count + 2,
              }
            : s,
        ),
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
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-3">
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
                activeSession === s.id ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              <p className="font-medium text-[13px] truncate">{s.title}</p>
              <p
                className={cn(
                  "text-[11px] mt-0.5 flex items-center gap-1",
                  activeSession === s.id ? "text-blue-100" : "text-slate-400",
                )}
              >
                <Clock className="h-2.5 w-2.5" />
                {formatDate(s.updated_at)}
              </p>
            </button>
          ))}
        </div>
      </div>

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
            <div key={msg.id} className={cn("flex gap-3 items-start", msg.role === "user" ? "justify-end" : "") }>
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
                    : "bg-white border border-slate-200 px-4 py-3 rounded-tl-sm shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]",
                )}
              >
                {msg.agent_name && (
                  <p
                    className={cn(
                      "text-[11px] font-medium mb-1.5 flex items-center gap-1",
                      msg.role === "assistant" ? "text-blue-600" : "text-blue-200",
                    )}
                  >
                    <Bot className="h-3 w-3" /> {msg.agent_name}
                  </p>
                )}

                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                {msg.status && (
                  <p
                    className={cn(
                      "mt-1 text-[11px] font-medium",
                      msg.status === "failed"
                        ? "text-red-600"
                        : msg.status === "completed"
                          ? "text-emerald-600"
                          : "text-blue-600",
                    )}
                  >
                    状态：
                    {msg.status === "in_progress"
                      ? "执行中"
                      : msg.status === "completed"
                        ? "已完成"
                        : "失败"}
                  </p>
                )}

                {msg.progress_events && msg.progress_events.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-100 space-y-1">
                    <p className="text-[11px] text-slate-500 font-medium">执行状态时间线</p>
                    <ProgressStatusItem
                      key={`${msg.id}-evt-latest`}
                      event={msg.progress_events[msg.progress_events.length - 1]}
                    />
                    {msg.progress_events.length > 1 && (
                      <details className="pt-1">
                        <summary className="cursor-pointer text-[11px] text-slate-500 hover:text-slate-700 select-none">
                          查看历史状态 ({msg.progress_events.length - 1})
                        </summary>
                        <div className="mt-1 space-y-1">
                          {msg.progress_events.slice(0, -1).map((event, idx) => (
                            <ProgressStatusItem key={`${msg.id}-evt-${idx}`} event={event} />
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {msg.reasoning_summary && (
                  <Card className="mt-3 p-2.5 border-slate-200">
                    <p className="text-[11px] text-slate-500 font-medium mb-1">思考摘要</p>
                    <p className="text-[11px] text-slate-700">意图理解：{msg.reasoning_summary.intent_understanding}</p>
                    <p className="text-[11px] text-slate-700">执行计划：{msg.reasoning_summary.execution_plan}</p>
                    <p className="text-[11px] text-slate-700">结果摘要：{msg.reasoning_summary.result_summary}</p>
                  </Card>
                )}

                {msg.tool_traces && msg.tool_traces.length > 0 && (
                  <div className={cn("mt-3 pt-2", msg.role === "assistant" ? "border-t border-slate-100" : "border-t border-blue-500/30")}>
                    <button
                      onClick={() => toggleTrace(msg.id)}
                      className={cn(
                        "flex items-center gap-1.5 text-[11px] font-medium transition-colors",
                        msg.role === "assistant" ? "text-slate-500 hover:text-slate-700" : "text-blue-200 hover:text-white",
                      )}
                    >
                      {expandedTraces.has(msg.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      工具调用 ({msg.tool_traces.length})
                    </button>
                    {expandedTraces.has(msg.id) && (
                      <div className="mt-2 space-y-1.5">
                        {msg.tool_traces.map((t, i) => (
                          <ToolTraceItem key={i} trace={t} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {msg.recommended_actions && msg.recommended_actions.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-100">
                    <p className="text-[11px] text-slate-500 mb-1.5 font-medium">建议动作</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.recommended_actions.map((a, i) => (
                        <Badge key={i} variant="info" className="cursor-pointer hover:bg-sky-100 transition-colors">
                          {a}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

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

                {msg.export_file && (
                  <div className="mt-3 pt-2 border-t border-slate-100 space-y-1.5">
                    <a
                      href={msg.export_file.download_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 hover:text-blue-800 transition-colors"
                    >
                      <ExternalLink className="h-3 w-3" />
                      下载导出文件 (CSV)
                    </a>
                    <p className="text-[11px] text-slate-500">链接有效期至：{formatDate(msg.export_file.expires_at)}</p>
                    {msg.export_columns && msg.export_columns.length > 0 && (
                      <p className="text-[11px] text-slate-500">已导出列：{msg.export_columns.join(",")}</p>
                    )}
                    {msg.ignored_columns && msg.ignored_columns.length > 0 && (
                      <p className="text-[11px] text-amber-600">已忽略列：{msg.ignored_columns.join(",")}</p>
                    )}
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

        <div className="rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)] p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入运维问题或指令，例如：分析 ESX-04 的 CPU 告警原因"
              rows={2}
              disabled={sending}
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700 placeholder:text-slate-400
                         focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all
                         disabled:opacity-60"
            />
            <Link href={executionHref}>
              <Button size="md" variant="secondary" className="shrink-0 self-end">
                <Play className="h-4 w-4" />
                执行申请
              </Button>
            </Link>
            <Button size="md" className="shrink-0 self-end" onClick={handleSend} disabled={sending || !input.trim()}>
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              发送
            </Button>
          </div>
          <p className="text-[11px] text-slate-400 mt-1.5 pl-0.5">支持自然语言，AI 将自动调用相关工具诊断 · Enter 发送，Shift+Enter 换行</p>
        </div>
      </div>

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
                        <div className="h-full rounded-full bg-blue-500" style={{ width: `${e.confidence * 100}%` }} />
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
