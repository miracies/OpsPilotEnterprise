"use client";

import { useCallback, useEffect, useRef, useState, type ComponentType, type KeyboardEvent } from "react";
import Link from "next/link";
import {
  Bot,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  Clock,
  ExternalLink,
  FileText,
  Loader2,
  Play,
  Plus,
  Send,
  Sparkles,
  User,
  Wrench,
  XCircle,
} from "lucide-react";

import { apiFetch } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { ChatMessage, ChatSession, ToolTrace } from "@opspilot/shared-types";

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
      <Wrench className="h-3 w-3 shrink-0 text-slate-400" />
      <span className="font-semibold text-blue-400">{trace.tool_name}</span>
      <span className="text-slate-500">&rarr;</span>
      <span className="flex-1 truncate text-slate-300">{trace.output_summary}</span>
      <span className="shrink-0 text-slate-500">{trace.duration_ms}ms</span>
      {isOk ? (
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
      ) : (
        <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />
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
      <span className="truncate text-slate-600">{event.text}</span>
      <span className="shrink-0 text-slate-400">{formatDate(event.ts)}</span>
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
      .then((res) => setSessions(res.data ?? []))
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
    const hasInProgress = messages.some((item) => item.status === "in_progress");
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
      setSessions((prev) => [res.data, ...prev]);
      setActiveSession(res.data.id);
    } catch {}
  }

  async function handleSend() {
    if (!input.trim() || sending) return;

    let sessionId = activeSession;
    if (!sessionId) {
      try {
        const res = await apiFetch<{ data: ChatSession }>("/api/v1/chat/sessions", {
          method: "POST",
          body: JSON.stringify({ title: input.trim().slice(0, 30) }),
        });
        sessionId = res.data.id;
        setSessions((prev) => [res.data, ...prev]);
        setActiveSession(sessionId);
      } catch {
        return;
      }
    }

    const userMsg: ChatMessage = {
      id: `tmp-${Date.now()}`,
      session_id: sessionId,
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const res = await apiFetch<{ data: ChatMessage }>(`/api/v1/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message: userMsg.content }),
      });
      const assistantMsg = res.data;
      setMessages((prev) => [...prev, assistantMsg]);

      if (assistantMsg.tool_traces && assistantMsg.tool_traces.length > 0) {
        setExpandedTraces((prev) => new Set([...prev, assistantMsg.id]));
      }

      const evRes = await apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${sessionId}/evidence`);
      setEvidence(evRes.data ?? []);

      setSessions((prev) =>
        prev.map((item) =>
          item.id === sessionId
            ? {
                ...item,
                title: userMsg.content.slice(0, 30),
                updated_at: new Date().toISOString(),
                message_count: item.message_count + 2,
              }
            : item,
        ),
      );
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          session_id: sessionId!,
          role: "assistant",
          content: "抱歉，消息发送失败，请稍后重试。",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  }

  const toggleTrace = (messageId: string) => {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) next.delete(messageId);
      else next.add(messageId);
      return next;
    });
  };

  return (
    <div className="flex h-[calc(100vh-8.5rem)] gap-3">
      <div className="flex w-56 shrink-0 flex-col gap-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">会话列表</span>
          <Button variant="ghost" size="icon" onClick={createSession}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {sessions.length === 0 && (
            <div className="flex flex-col items-center py-10 text-center">
              <p className="text-xs text-slate-400">暂无会话</p>
              <p className="mt-1 text-[11px] text-slate-300">点击 + 创建新会话</p>
            </div>
          )}
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => setActiveSession(session.id)}
              className={cn(
                "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-all duration-150",
                activeSession === session.id ? "bg-blue-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              <p className="truncate text-[13px] font-medium">{session.title}</p>
              <p
                className={cn(
                  "mt-0.5 flex items-center gap-1 text-[11px]",
                  activeSession === session.id ? "text-blue-100" : "text-slate-400",
                )}
              >
                <Clock className="h-2.5 w-2.5" />
                {formatDate(session.updated_at)}
              </p>
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 space-y-5 overflow-y-auto pb-4 pr-1">
          {messages.length === 0 && !sending && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Sparkles className="mb-3 h-10 w-10 text-blue-200" />
              <p className="text-sm font-medium text-slate-500">开始新的运维对话</p>
              <p className="mt-1 text-xs text-slate-400">输入运维问题或指令，AI 会自动调用相关工具分析。</p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={cn("flex items-start gap-3", message.role === "user" ? "justify-end" : "")}>
              {message.role === "assistant" && (
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700 shadow-sm">
                  <Sparkles className="h-3.5 w-3.5 text-white" />
                </div>
              )}

              <div
                className={cn(
                  "max-w-[72%] rounded-2xl text-sm",
                  message.role === "user"
                    ? "rounded-tr-sm bg-blue-600 px-4 py-3 text-white shadow-sm"
                    : "rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]",
                )}
              >
                {message.agent_name && (
                  <p
                    className={cn(
                      "mb-1.5 flex items-center gap-1 text-[11px] font-medium",
                      message.role === "assistant" ? "text-blue-600" : "text-blue-200",
                    )}
                  >
                    <Bot className="h-3 w-3" /> {message.agent_name}
                  </p>
                )}

                <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>

                {message.status && (
                  <p
                    className={cn(
                      "mt-1 text-[11px] font-medium",
                      message.status === "failed"
                        ? "text-red-600"
                        : message.status === "completed"
                          ? "text-emerald-600"
                          : "text-blue-600",
                    )}
                  >
                    状态：
                    {message.status === "in_progress"
                      ? "执行中"
                      : message.status === "completed"
                        ? "已完成"
                        : "失败"}
                  </p>
                )}

                {message.progress_events && message.progress_events.length > 0 && (
                  <div className="mt-3 space-y-1 border-t border-slate-100 pt-2">
                    <p className="text-[11px] font-medium text-slate-500">执行状态时间线</p>
                    <ProgressStatusItem
                      key={`${message.id}-evt-latest`}
                      event={message.progress_events[message.progress_events.length - 1]}
                    />
                    {message.progress_events.length > 1 && (
                      <details className="pt-1">
                        <summary className="cursor-pointer select-none text-[11px] text-slate-500 hover:text-slate-700">
                          查看历史状态 ({message.progress_events.length - 1})
                        </summary>
                        <div className="mt-1 space-y-1">
                          {message.progress_events.slice(0, -1).map((event, idx) => (
                            <ProgressStatusItem key={`${message.id}-evt-${idx}`} event={event} />
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                )}

                {message.reasoning_summary && (
                  <Card className="mt-3 border-slate-200 p-2.5">
                    <p className="mb-1 text-[11px] font-medium text-slate-500">思考摘要</p>
                    <p className="text-[11px] text-slate-700">意图理解：{message.reasoning_summary.intent_understanding}</p>
                    <p className="text-[11px] text-slate-700">执行计划：{message.reasoning_summary.execution_plan}</p>
                    <p className="text-[11px] text-slate-700">结果摘要：{message.reasoning_summary.result_summary}</p>
                  </Card>
                )}

                {(message.conclusion_status ||
                  message.evidence_sufficiency ||
                  (message.hypotheses && message.hypotheses.length > 0)) && (
                  <Card className="mt-3 border-slate-200 bg-slate-50/60 p-2.5">
                    <div className="space-y-1.5 text-[11px] text-slate-700">
                      {message.conclusion_status && (
                        <p>
                          <span className="font-medium text-slate-500">结论状态：</span>
                          {message.conclusion_status}
                        </p>
                      )}
                      {message.evidence_sufficiency && (
                        <>
                          <p>
                            <span className="font-medium text-slate-500">证据充分性：</span>
                            {(message.evidence_sufficiency.sufficiency_score ?? 0).toFixed(2)} / 新鲜度{" "}
                            {(message.evidence_sufficiency.freshness_score ?? 0).toFixed(2)}
                          </p>
                          {message.evidence_sufficiency.missing_critical_evidence?.length > 0 && (
                            <p>
                              <span className="font-medium text-amber-700">缺失关键证据：</span>
                              {message.evidence_sufficiency.missing_critical_evidence.join("、")}
                            </p>
                          )}
                        </>
                      )}
                      {message.counter_evidence_result && (
                        <p>
                          <span className="font-medium text-slate-500">反证结果：</span>
                          {message.counter_evidence_result.status}，{message.counter_evidence_result.summary}
                        </p>
                      )}
                      {message.hypotheses && message.hypotheses.length > 0 && (
                        <div className="pt-1">
                          <p className="mb-1 font-medium text-slate-500">候选根因</p>
                          <div className="space-y-1">
                            {message.hypotheses.slice(0, 3).map((item) => (
                              <div key={item.id} className="rounded border border-slate-200 bg-white px-2 py-1">
                                <div className="font-medium text-slate-800">
                                  {item.summary} ({(item.confidence ?? 0).toFixed(2)})
                                </div>
                                {item.missing_evidence?.length > 0 && (
                                  <div className="text-amber-700">缺口：{item.missing_evidence.join("、")}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </Card>
                )}

                {message.tool_traces && message.tool_traces.length > 0 && (
                  <div
                    className={cn(
                      "mt-3 pt-2",
                      message.role === "assistant" ? "border-t border-slate-100" : "border-t border-blue-500/30",
                    )}
                  >
                    <button
                      onClick={() => toggleTrace(message.id)}
                      className={cn(
                        "flex items-center gap-1.5 text-[11px] font-medium transition-colors",
                        message.role === "assistant"
                          ? "text-slate-500 hover:text-slate-700"
                          : "text-blue-200 hover:text-white",
                      )}
                    >
                      {expandedTraces.has(message.id) ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                      工具调用 ({message.tool_traces.length})
                    </button>
                    {expandedTraces.has(message.id) && (
                      <div className="mt-2 space-y-1.5">
                        {message.tool_traces.map((item, idx) => (
                          <ToolTraceItem key={`${message.id}-trace-${idx}`} trace={item} />
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {message.recommended_actions && message.recommended_actions.length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-2">
                    <p className="mb-1.5 text-[11px] font-medium text-slate-500">建议动作</p>
                    <div className="flex flex-wrap gap-1.5">
                      {message.recommended_actions.map((action, idx) => (
                        <Badge key={`${message.id}-action-${idx}`} variant="info" className="cursor-pointer hover:bg-sky-100">
                          {action}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {message.diagnosis_id && (
                  <div className="mt-3 border-t border-slate-100 pt-2">
                    <a
                      href={`/diagnosis?diagnosis_id=${message.diagnosis_id}`}
                      className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 transition-colors hover:text-blue-800"
                    >
                      <ExternalLink className="h-3 w-3" />
                      查看诊断详情
                    </a>
                  </div>
                )}

                {message.export_file && (
                  <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2">
                    <a
                      href={message.export_file.download_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 transition-colors hover:text-blue-800"
                    >
                      <ExternalLink className="h-3 w-3" />
                      下载导出文件 (CSV)
                    </a>
                    <p className="text-[11px] text-slate-500">链接有效期至：{formatDate(message.export_file.expires_at)}</p>
                    {message.export_columns && message.export_columns.length > 0 && (
                      <p className="text-[11px] text-slate-500">已导出列：{message.export_columns.join(",")}</p>
                    )}
                    {message.ignored_columns && message.ignored_columns.length > 0 && (
                      <p className="text-[11px] text-amber-600">已忽略列：{message.ignored_columns.join(",")}</p>
                    )}
                  </div>
                )}
              </div>

              {message.role === "user" && (
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700">
                  <User className="h-3.5 w-3.5 text-slate-200" />
                </div>
              )}
            </div>
          ))}

          {sending && (
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700 shadow-sm">
                <Sparkles className="h-3.5 w-3.5 text-white" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在分析中...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入运维问题或指令，例如：分析 ESX-04 的 CPU 告警原因"
              rows={2}
              disabled={sending}
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700 transition-all placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-60"
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
          <p className="mt-1.5 pl-0.5 text-[11px] text-slate-400">
            支持自然语言，AI 会自动调用相关工具诊断。Enter 发送，Shift+Enter 换行。
          </p>
        </div>
      </div>

      <div className="w-64 shrink-0 space-y-3 overflow-y-auto">
        <div className="px-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">关联证据</span>
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {evidence.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
              <FileText className="mb-2 h-8 w-8 text-slate-200" />
              <p className="text-xs text-slate-400">暂无关联证据</p>
              <p className="mt-0.5 text-[11px] text-slate-300">发送诊断请求后将显示证据</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {evidence.map((item) => (
                <div key={item.evidence_id} className="p-3 transition-colors hover:bg-slate-50">
                  <div className="mb-1.5 flex items-center justify-between">
                    <Badge variant="neutral">{item.source_type}</Badge>
                    <div className="flex items-center gap-1">
                      <div className="h-1 w-14 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-blue-500" style={{ width: `${item.confidence * 100}%` }} />
                      </div>
                      <span className="text-[11px] text-slate-500">{(item.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-700">{item.summary}</p>
                  <p className="mt-1 text-[11px] text-slate-400">{formatDate(item.timestamp)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

