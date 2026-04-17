"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ComponentType, type KeyboardEvent } from "react";
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

import type { ChatMessage, ChatSession, ToolTrace } from "@opspilot/shared-types";

import { ApprovalCard } from "@/components/chat/ApprovalCard";
import { AuditTimeline } from "@/components/chat/AuditTimeline";
import { ClarifyCard } from "@/components/chat/ClarifyCard";
import { IntentRecoveryCard } from "@/components/chat/IntentRecoveryCard";
import { ResumeCard } from "@/components/chat/ResumeCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

interface Evidence {
  evidence_id: string;
  source_type: string;
  summary: string;
  confidence: number;
  timestamp: string;
}

const CHAT_MODE = process.env.NEXT_PUBLIC_CHAT_MODE ?? "legacy";

function ToolTraceItem({ trace }: { trace: ToolTrace }) {
  const isOk = trace.status === "success";
  return (
    <div className="flex items-center gap-2 rounded-md bg-slate-900 px-3 py-2 font-mono text-[11px]">
      <Wrench className="h-3 w-3 shrink-0 text-slate-400" />
      <span className="font-semibold text-blue-400">{trace.tool_name}</span>
      <span className="text-slate-500">&rarr;</span>
      <span className="flex-1 truncate text-slate-300">{trace.output_summary}</span>
      <span className="shrink-0 text-slate-500">{trace.duration_ms}ms</span>
      {isOk ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}
    </div>
  );
}

function ProgressStatusItem({ event }: { event: NonNullable<ChatMessage["progress_events"]>[number] }) {
  const stageMeta: Record<
    NonNullable<ChatMessage["progress_events"]>[number]["stage"],
    { label: string; icon: ComponentType<{ className?: string }>; color: string; badgeBg: string }
  > = {
    received: { label: "已接收请求", icon: CircleDashed, color: "text-slate-600", badgeBg: "bg-slate-100" },
    intent_parsed: { label: "意图识别中", icon: Brain, color: "text-violet-600", badgeBg: "bg-violet-100" },
    agent_selected: { label: "Agent 选择中", icon: Bot, color: "text-indigo-600", badgeBg: "bg-indigo-100" },
    tool_invoking: { label: "调用工具中", icon: Wrench, color: "text-blue-600", badgeBg: "bg-blue-100" },
    tool_done: { label: "工具调用完成", icon: CheckCircle2, color: "text-emerald-600", badgeBg: "bg-emerald-100" },
    tool_error: { label: "工具调用失败", icon: XCircle, color: "text-red-600", badgeBg: "bg-red-100" },
    completed: { label: "汇总结果中", icon: CheckCircle2, color: "text-emerald-700", badgeBg: "bg-emerald-100" },
    failed: { label: "任务失败", icon: XCircle, color: "text-red-700", badgeBg: "bg-red-100" },
  };
  const meta = stageMeta[event.stage];
  const StatusIcon = meta.icon;
  const statusText = event.status === "error" ? "失败" : event.status === "success" ? "完成" : "进行中";
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5", meta.badgeBg)}>
        <StatusIcon className={cn("h-3.5 w-3.5", meta.color)} />
        <span className={cn("font-medium", meta.color)}>{meta.label}</span>
      </span>
      <span className="text-slate-500">{statusText}</span>
      <span className="truncate text-slate-600">{event.text}</span>
      <span className="shrink-0 text-slate-400">{formatDate(event.ts)}</span>
    </div>
  );
}

function buildWorkflowStages(nextAction: string, detail?: string) {
  const base: Array<{
    key: string;
    label: string;
    status: "done" | "active" | "pending";
    detail: string;
  }> = [
    { key: "recover", label: "意图恢复", status: "done" as const, detail: "已完成" },
    { key: "clarify", label: "澄清补槽", status: "done" as const, detail: "已完成" },
    { key: "approve", label: "审批门禁", status: "pending" as const, detail: "等待中" },
    { key: "execute", label: "执行与审计", status: "pending" as const, detail: "等待中" },
  ];
  if (nextAction === "clarify_pending") {
    base[1] = { ...base[1], status: "active", detail: detail || "需要继续补充信息" };
    base[2] = { ...base[2], status: "pending", detail: "待澄清完成" };
  } else if (nextAction === "approval_pending") {
    base[2] = { ...base[2], status: "active", detail: detail || "等待审批决策" };
  } else if (nextAction === "executed") {
    base[2] = { ...base[2], status: "done", detail: "审批通过" };
    base[3] = { ...base[3], status: "done", detail: detail || "已自动执行并写入审计" };
  } else if (nextAction === "recovered") {
    base[2] = { ...base[2], status: "pending", detail: "动作风险判定中" };
  } else if (nextAction === "stop") {
    base[2] = { ...base[2], status: "done", detail: "审批拒绝/终止" };
    base[3] = { ...base[3], status: "pending", detail: "未执行" };
  } else {
    base[2] = { ...base[2], status: "active", detail: detail || "处理中" };
  }
  return base;
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

  const activeInProgress = useMemo(() => messages.some((item) => item.status === "in_progress"), [messages]);

  useEffect(() => {
    apiFetch<{ data: ChatSession[] }>("/api/v1/chat/sessions").then((res) => setSessions(res.data ?? [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeSession) {
      setMessages([]);
      setEvidence([]);
      return;
    }
    apiFetch<{ data: ChatMessage[] }>(`/api/v1/chat/sessions/${activeSession}/messages`).then((res) => setMessages(res.data ?? [])).catch(() => setMessages([]));
    apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${activeSession}/evidence`).then((res) => setEvidence(res.data ?? [])).catch(() => setEvidence([]));
  }, [activeSession]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (!activeSession || !activeInProgress) return;
    const timer = setInterval(() => {
      apiFetch<{ data: ChatMessage[] }>(`/api/v1/chat/sessions/${activeSession}/messages`).then((res) => setMessages(res.data ?? [])).catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [activeSession, activeInProgress]);

  async function createSession() {
    const res = await apiFetch<{ data: ChatSession }>("/api/v1/chat/sessions", { method: "POST", body: JSON.stringify({ title: null }) });
    setSessions((prev) => [res.data, ...prev]);
    setActiveSession(res.data.id);
  }

  async function handleSend() {
    if (!input.trim() || sending) return;
    let sessionId = activeSession;
    if (!sessionId) {
      const res = await apiFetch<{ data: ChatSession }>("/api/v1/chat/sessions", {
        method: "POST",
        body: JSON.stringify({ title: input.trim().slice(0, 30) }),
      });
      sessionId = res.data.id;
      setSessions((prev) => [res.data, ...prev]);
      setActiveSession(sessionId);
    }
    const userMsg: ChatMessage = { id: `tmp-${Date.now()}`, session_id: sessionId, role: "user", content: input.trim(), timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const res = await apiFetch<{ data: ChatMessage }>(`/api/v1/chat/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ message: userMsg.content, mode: CHAT_MODE === "orchestrator_v2" ? "orchestrator_v2" : undefined }),
      });
      setMessages((prev) => [...prev, res.data]);
      const evRes = await apiFetch<{ data: Evidence[] }>(`/api/v1/chat/sessions/${sessionId}/evidence`);
      setEvidence(evRes.data ?? []);
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

  function toggleTrace(messageId: string) {
    setExpandedTraces((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) next.delete(messageId);
      else next.add(messageId);
      return next;
    });
  }

  function appendAssistantFromInteraction(payload: Record<string, unknown>) {
    if (!activeSession) return;
    const nextAction = String(payload.next_action ?? "done");
    const nextMessageText = String(payload.next_message ?? "已处理本次交互。");
    const trigger = payload.approval_card ? "approval" : payload.clarify_card ? "clarify" : "system";
    const nextMessage: ChatMessage = {
      id: `msg-local-${Date.now()}`,
      session_id: activeSession,
      role: "assistant",
      content: nextMessageText,
      timestamp: new Date().toISOString(),
      kind: "text",
      workflow_update: {
        trigger,
        next_action: nextAction,
        stages: buildWorkflowStages(nextAction, nextMessageText),
        updated_at: new Date().toISOString(),
      },
      intent_recovery: payload.intent_recovery as ChatMessage["intent_recovery"],
      clarify_card: payload.clarify_card as ChatMessage["clarify_card"],
      approval_card: payload.approval_card as ChatMessage["approval_card"],
      resume_card: payload.resume_card as ChatMessage["resume_card"],
      audit_timeline: payload.audit_timeline as ChatMessage["audit_timeline"],
      status: "completed",
      reasoning_summary: {
        intent_understanding: "交互结果已回传到会话。",
        execution_plan: "根据后端 next_action 自动衔接下一步。",
        result_summary: nextAction,
      },
      agent_name: "OrchestratorV2",
    };
    setMessages((prev) => [...prev, nextMessage]);
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] gap-4">
      <div className="w-64 shrink-0 rounded-xl border border-slate-200 bg-white p-3 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">AI 对话</p>
            <p className="text-[11px] text-slate-500">模式：{CHAT_MODE}</p>
          </div>
          <Button size="sm" variant="secondary" onClick={() => void createSession()}>
            <Plus className="h-3.5 w-3.5" /> 新建
          </Button>
        </div>
        <div className="space-y-2">
          {sessions.map((session) => (
            <button key={session.id} onClick={() => setActiveSession(session.id)} className={cn("w-full rounded-lg border px-3 py-2 text-left", activeSession === session.id ? "border-blue-300 bg-blue-50" : "border-slate-200 hover:bg-slate-50")}>
              <p className="truncate text-sm font-medium text-slate-800">{session.title}</p>
              <p className="mt-1 flex items-center gap-1 text-[11px] text-slate-400"><Clock className="h-2.5 w-2.5" />{formatDate(session.updated_at)}</p>
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
              <p className="mt-1 text-xs text-slate-400">输入运维问题或指令，系统会按灰度模式调用旧链路或 Orchestrator V2。</p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={cn("flex items-start gap-3", message.role === "user" ? "justify-end" : "") }>
              {message.role === "assistant" && <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700"><Sparkles className="h-3.5 w-3.5 text-white" /></div>}
              <div className={cn("max-w-[72%] rounded-2xl text-sm", message.role === "user" ? "rounded-tr-sm bg-blue-600 px-4 py-3 text-white" : "rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]")}>
                {message.agent_name && <p className={cn("mb-1.5 flex items-center gap-1 text-[11px] font-medium", message.role === "assistant" ? "text-blue-600" : "text-blue-100")}><Bot className="h-3 w-3" />{message.agent_name}</p>}
                <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>

                {message.status && <p className={cn("mt-1 text-[11px] font-medium", message.status === "failed" ? "text-red-600" : message.status === "completed" ? "text-emerald-600" : "text-blue-600")}>状态：{message.status === "in_progress" ? "执行中" : message.status === "completed" ? "已完成" : "失败"}</p>}

                {message.progress_events && message.progress_events.length > 0 && (
                  <div className="mt-3 space-y-1 border-t border-slate-100 pt-2">
                    <p className="text-[11px] font-medium text-slate-500">执行状态时间线</p>
                    <ProgressStatusItem event={message.progress_events[message.progress_events.length - 1]} />
                    {message.progress_events.length > 1 && (
                      <details className="pt-1">
                        <summary className="cursor-pointer select-none text-[11px] text-slate-500 hover:text-slate-700">查看历史状态 ({message.progress_events.length - 1})</summary>
                        <div className="mt-1 space-y-1">{message.progress_events.slice(0, -1).map((event, idx) => <ProgressStatusItem key={`${message.id}-${idx}`} event={event} />)}</div>
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

                {message.workflow_update && (
                  <Card className="mt-3 border-sky-200 bg-sky-50/50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-[11px] font-semibold text-sky-700">卡片交互后自动推进</p>
                      <Badge variant="info">{message.workflow_update.next_action}</Badge>
                    </div>
                    <div className="space-y-2">
                      {message.workflow_update.stages.map((stage) => {
                        const tone =
                          stage.status === "done"
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : stage.status === "active"
                              ? "border-blue-300 bg-blue-50 text-blue-700"
                              : "border-slate-200 bg-white text-slate-500";
                        const dot =
                          stage.status === "done"
                            ? "bg-emerald-500"
                            : stage.status === "active"
                              ? "bg-blue-500"
                              : "bg-slate-300";
                        return (
                          <div key={stage.key} className={cn("rounded-lg border px-2 py-2", tone)}>
                            <div className="flex items-center gap-2">
                              <span className={cn("h-2.5 w-2.5 rounded-full", dot)} />
                              <p className="text-xs font-medium">{stage.label}</p>
                            </div>
                            <p className="mt-1 pl-4 text-[11px]">{stage.detail}</p>
                          </div>
                        );
                      })}
                    </div>
                  </Card>
                )}

                {message.intent_recovery && <IntentRecoveryCard run={message.intent_recovery} />}
                {message.clarify_card && <ClarifyCard record={message.clarify_card} onResolved={appendAssistantFromInteraction} />}
                {message.approval_card && <ApprovalCard record={message.approval_card} onResolved={appendAssistantFromInteraction} />}
                {message.resume_card && <ResumeCard record={message.resume_card} />}
                {message.audit_timeline && <AuditTimeline data={message.audit_timeline} />}

                {message.tool_traces && message.tool_traces.length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-2">
                    <button onClick={() => toggleTrace(message.id)} className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500 hover:text-slate-700">
                      {expandedTraces.has(message.id) ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      工具调用 ({message.tool_traces.length})
                    </button>
                    {expandedTraces.has(message.id) && <div className="mt-2 space-y-1.5">{message.tool_traces.map((item, idx) => <ToolTraceItem key={`${message.id}-${idx}`} trace={item} />)}</div>}
                  </div>
                )}

                {message.export_file && (
                  <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-2">
                    <a href={message.export_file.download_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 hover:text-blue-800">
                      <ExternalLink className="h-3 w-3" /> 下载导出文件 (CSV)
                    </a>
                    <p className="text-[11px] text-slate-500">链接有效期至：{formatDate(message.export_file.expires_at)}</p>
                  </div>
                )}

                {message.diagnosis_id && (
                  <div className="mt-3 border-t border-slate-100 pt-2">
                    <a href={`/diagnosis?diagnosis_id=${message.diagnosis_id}`} className="inline-flex items-center gap-1.5 text-[12px] font-medium text-blue-600 hover:text-blue-800">
                      <ExternalLink className="h-3 w-3" /> 查看诊断详情
                    </a>
                  </div>
                )}
              </div>
              {message.role === "user" && <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-slate-700"><User className="h-3.5 w-3.5 text-slate-200" /></div>}
            </div>
          ))}

          {sending && (
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-700"><Sparkles className="h-3.5 w-3.5 text-white" /></div>
              <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />正在发送...</div>
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
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <Link href={executionHref}><Button size="md" variant="secondary"><Play className="h-4 w-4" />执行申请</Button></Link>
            <Button size="md" onClick={() => void handleSend()} disabled={sending || !input.trim()}>{sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}发送</Button>
          </div>
          <p className="mt-1.5 pl-0.5 text-[11px] text-slate-400">支持自然语言；Enter 发送，Shift+Enter 换行。</p>
        </div>
      </div>

      <div className="w-64 shrink-0 space-y-3 overflow-y-auto">
        <div className="px-1"><span className="text-xs font-semibold uppercase tracking-wider text-slate-500">关联证据</span></div>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {evidence.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-4 py-10 text-center"><FileText className="mb-2 h-8 w-8 text-slate-200" /><p className="text-xs text-slate-400">暂无关联证据</p></div>
          ) : (
            <div className="divide-y divide-slate-50">
              {evidence.map((item) => (
                <div key={item.evidence_id} className="p-3 hover:bg-slate-50">
                  <div className="mb-1.5 flex items-center justify-between"><Badge variant="neutral">{item.source_type}</Badge><span className="text-[11px] text-slate-500">{(item.confidence * 100).toFixed(0)}%</span></div>
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
