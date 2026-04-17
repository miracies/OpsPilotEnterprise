"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Clock, FileText, User, XCircle } from "lucide-react";
import type { ApprovalRequest } from "@opspilot/shared-types";

import { Badge, RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { apiFetch } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

type ApprovalsListEnvelope = { success: boolean; error?: string; data?: { items?: ApprovalRequest[]; total?: number } };
type ApprovalDetailEnvelope = { success: boolean; error?: string; data?: ApprovalRequest };

const STATUS_TABS = [
  { key: "all", label: "全部" },
  { key: "pending", label: "待审批" },
  { key: "approved", label: "已通过" },
  { key: "rejected", label: "已驳回" },
  { key: "expired", label: "已过期" },
] as const;

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 ring-amber-600/20",
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  rejected: "bg-red-50 text-red-700 ring-red-600/20",
  expired: "bg-slate-100 text-slate-500 ring-slate-300",
  recalled: "bg-slate-100 text-slate-500 ring-slate-300",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "待审批",
  approved: "已通过",
  rejected: "已驳回",
  expired: "已过期",
  recalled: "已撤回",
};

const DEFAULT_DECIDER = "ops-user";

export default function ApprovalsPage() {
  const [filter, setFilter] = useState<(typeof STATUS_TABS)[number]["key"]>("all");
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApprovalRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionComment, setDecisionComment] = useState("");

  const loadApprovals = useCallback(async () => {
    const path = filter === "all" ? "/api/v1/approvals" : `/api/v1/approvals?status=${encodeURIComponent(filter)}`;
    const res = await apiFetch<ApprovalsListEnvelope>(path);
    if (!res.success) throw new Error(res.error || "加载审批列表失败");
    const items = res.data?.items ?? [];
    setApprovals(items);
    setSelectedId((prev) => (prev && items.some((item) => item.id === prev) ? prev : items[0]?.id ?? null));
  }, [filter]);

  const loadDetail = useCallback(async (approvalId: string | null) => {
    if (!approvalId) {
      setDetail(null);
      return;
    }
    const res = await apiFetch<ApprovalDetailEnvelope>(`/api/v1/approvals/${approvalId}`);
    if (!res.success || !res.data) throw new Error(res.error || "加载审批详情失败");
    setDetail(res.data);
  }, []);

  const refresh = useCallback(async () => {
    try {
      await loadApprovals();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载审批数据失败");
    } finally {
      setLoading(false);
    }
  }, [loadApprovals]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    void loadDetail(selectedId).catch((err) => setError(err instanceof Error ? err.message : "加载审批详情失败"));
  }, [selectedId, loadDetail]);

  useEffect(() => {
    const timer = setInterval(() => {
      void refresh();
      if (selectedId) void loadDetail(selectedId).catch(() => null);
    }, 5000);
    return () => clearInterval(timer);
  }, [refresh, selectedId, loadDetail]);

  const counts = useMemo(() => ({
    all: approvals.length,
    pending: approvals.filter((item) => item.status === "pending").length,
    approved: approvals.filter((item) => item.status === "approved").length,
    rejected: approvals.filter((item) => item.status === "rejected").length,
    expired: approvals.filter((item) => item.status === "expired").length,
  }), [approvals]);

  async function submitDecision(decision: "approved" | "rejected") {
    if (!detail || detail.status !== "pending") return;
    const comment = decisionComment.trim();
    if (decision === "rejected" && !comment) {
      setError("驳回时必须填写审批意见");
      return;
    }
    setSubmitting(true);
    try {
      const path = detail.approval_id ? `/api/v1/interactions/approve/${detail.approval_id}/decision` : `/api/v1/approvals/${detail.id}/decide`;
      const res = await apiFetch<{ success: boolean; error?: string }>(path, {
        method: "POST",
        body: JSON.stringify(detail.approval_id
          ? { decision, scope: detail.allowed_scopes?.[0] ?? "once", comment: comment || null, approved_by: DEFAULT_DECIDER }
          : { decision, decided_by: DEFAULT_DECIDER, comment: comment || null }),
      });
      if (!res.success) throw new Error(res.error || "提交审批结果失败");
      setDecisionComment("");
      await refresh();
      await loadDetail(detail.id);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交审批结果失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col">
      <PageHeader
        title="审批中心"
        description="查看并处理待审批执行请求，联动真实审批数据流。"
        actions={<div className="flex items-center gap-2"><span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">{counts.pending} 项待审批</span><Button variant="secondary" size="sm" onClick={() => void refresh()}>刷新</Button></div>}
      />

      <div className="mb-4 flex items-center gap-1 border-b border-slate-200">
        {STATUS_TABS.map((tab) => (
          <button key={tab.key} onClick={() => setFilter(tab.key)} className={cn("border-b-2 -mb-px px-4 py-2.5 text-sm font-medium transition-all", filter === tab.key ? "border-blue-600 text-blue-700" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700")}>
            {tab.label}
            <span className={cn("ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold", filter === tab.key ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500")}>{counts[tab.key]}</span>
          </button>
        ))}
      </div>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}
      {loading && <div className="mb-3 text-sm text-slate-500">正在加载审批数据...</div>}

      <div className="flex min-h-0 flex-1 gap-4">
        <div className="flex-1 overflow-auto rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {approvals.length === 0 ? (
            <div className="p-6 text-sm text-slate-500">当前筛选下暂无审批记录</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">申请标题</th>
                  <th className="w-24 px-3 py-3 text-left text-xs font-semibold text-slate-500">动作类型</th>
                  <th className="w-24 px-3 py-3 text-left text-xs font-semibold text-slate-500">风险等级</th>
                  <th className="w-20 px-3 py-3 text-left text-xs font-semibold text-slate-500">状态</th>
                  <th className="w-24 px-3 py-3 text-left text-xs font-semibold text-slate-500">申请人</th>
                  <th className="w-36 px-3 py-3 text-left text-xs font-semibold text-slate-500">申请时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {approvals.map((apr) => (
                  <tr key={apr.id} onClick={() => setSelectedId(apr.id)} className={cn("cursor-pointer transition-colors hover:bg-slate-50", selectedId === apr.id ? "bg-blue-50" : "", apr.status === "pending" ? "border-l-2 border-l-amber-400" : "") }>
                    <td className="px-5 py-3"><p className="max-w-[260px] truncate font-medium text-slate-900">{apr.title}</p><p className="mt-0.5 font-mono text-[11px] text-slate-400">{apr.id}</p></td>
                    <td className="px-3 py-3"><Badge variant="neutral">{apr.action_type}</Badge></td>
                    <td className="px-3 py-3"><RiskBadge level={apr.risk_level} /></td>
                    <td className="px-3 py-3"><span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", STATUS_STYLE[apr.status] ?? STATUS_STYLE.expired)}>{STATUS_LABEL[apr.status] ?? apr.status}</span></td>
                    <td className="px-3 py-3 text-xs text-slate-600">{apr.requester}</td>
                    <td className="px-3 py-3 text-xs text-slate-500"><span className="flex items-center gap-1"><Clock className="h-3 w-3 text-slate-300" />{formatDate(apr.created_at)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="w-96 shrink-0 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-[0_1px_3px_0_rgb(0_0_0/0.06)]">
          {!detail ? (
            <div className="p-6 text-sm text-slate-500">请选择一条审批记录查看详情</div>
          ) : (
            <>
              <div className="border-b border-slate-100 border-l-4 border-l-blue-500 px-4 py-3">
                <div className="mb-1.5 flex items-center justify-between"><RiskBadge level={detail.risk_level} /><span className={cn("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", STATUS_STYLE[detail.status] ?? STATUS_STYLE.expired)}>{STATUS_LABEL[detail.status] ?? detail.status}</span></div>
                <h3 className="text-sm font-semibold text-slate-900">{detail.title}</h3>
                <p className="mt-0.5 font-mono text-[11px] text-slate-400">{detail.id}</p>
              </div>

              <div className="space-y-5 px-4 py-4">
                <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">变更描述</p><p className="text-xs leading-relaxed text-slate-700">{detail.summary ?? detail.description}</p></div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5"><p className="mb-0.5 text-[10px] text-slate-400">目标对象</p><p className="text-xs font-medium text-slate-700">{detail.target_object}</p><p className="text-[10px] text-slate-400">{detail.target_object_type}</p></div>
                  <div className="rounded-lg border border-slate-100 bg-slate-50 p-2.5"><p className="mb-0.5 text-[10px] text-slate-400">风险评分</p><p className="text-lg font-bold text-slate-800">{detail.risk_score}</p><p className="text-[10px] text-slate-400">/ 100</p></div>
                </div>

                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">审批流展示</p>
                  <div className="space-y-1.5 text-xs text-slate-700">
                    <div className="flex items-center gap-2"><User className="h-3.5 w-3.5 text-slate-400" /><span className="text-slate-500">申请人：</span><span className="font-medium">{detail.requester}</span></div>
                    <div className="flex items-center gap-2"><User className="h-3.5 w-3.5 text-slate-400" /><span className="text-slate-500">审批人：</span><span className="font-medium">{detail.assignee ?? "未指派"}</span></div>
                    {detail.incident_ref && <div className="flex items-center gap-2"><AlertTriangle className="h-3.5 w-3.5 text-slate-400" /><span className="text-slate-500">关联事件：</span><Link href="/incidents" className="font-medium text-blue-600 hover:underline">{detail.incident_ref}</Link></div>}
                    {detail.change_analysis_ref && <div className="flex items-center gap-2"><FileText className="h-3.5 w-3.5 text-slate-400" /><span className="text-slate-500">变更分析：</span><Link href="/change-impact" className="font-medium text-blue-600 hover:underline">{detail.change_analysis_ref}</Link></div>}
                    {detail.expires_at && <div className="flex items-center gap-2"><Clock className="h-3.5 w-3.5 text-slate-400" /><span className="text-slate-500">过期时间：</span><span className="font-medium text-amber-600">{formatDate(detail.expires_at)}</span></div>}
                  </div>
                </div>

                {(detail.plan_steps?.length || detail.rollback_plan?.length || detail.allowed_scopes?.length) && (
                  <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-700">
                    <p className="mb-1.5 font-semibold text-slate-500">执行计划与回滚</p>
                    {detail.plan_steps?.length ? <p>计划步骤：{detail.plan_steps.join(" -> ")}</p> : null}
                    {detail.rollback_plan?.length ? <p className="mt-1">回滚方案：{detail.rollback_plan.join("；")}</p> : null}
                    {detail.allowed_scopes?.length ? <p className="mt-1">允许作用域：{detail.allowed_scopes.join(" / ")}</p> : null}
                    {detail.resource_scope?.resources?.length ? <p className="mt-1">资源范围：{detail.resource_scope.resources.map((item) => item.name || item.id).join("、")}</p> : null}
                  </div>
                )}

                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">审批意见</p>
                  <textarea className="min-h-[88px] w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500" value={decisionComment} onChange={(event) => setDecisionComment(event.target.value)} placeholder="驳回时必须填写审批意见；通过可选。" disabled={detail.status !== "pending" || submitting} />
                </div>

                {detail.decision_comment && <div><p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">已记录结果</p><div className={cn("rounded-lg border px-3 py-2.5 text-xs", detail.status === "approved" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : detail.status === "rejected" ? "border-red-200 bg-red-50 text-red-700" : "border-slate-100 bg-slate-50 text-slate-700")}>{detail.decision_comment}</div><p className="mt-1 text-[11px] text-slate-400">{detail.decided_by} · {detail.decided_at ? formatDate(detail.decided_at) : "-"}</p></div>}

                {detail.status === "pending" && <div className="flex gap-2 pt-1"><Button variant="primary" size="sm" className="flex-1" disabled={submitting} onClick={() => void submitDecision("approved")}><CheckCircle2 className="h-3.5 w-3.5" />通过</Button><Button variant="secondary" size="sm" className="flex-1 border-red-200 text-red-600 hover:bg-red-50" disabled={submitting} onClick={() => void submitDecision("rejected")}><XCircle className="h-3.5 w-3.5" />驳回</Button></div>}

                <div className="flex flex-wrap gap-2">{detail.tags.map((tag) => <Badge key={tag} variant="neutral">{tag}</Badge>)}</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
