"use client";

import { useState, useEffect, useCallback } from "react";
import {
  KeyRound, Search, Plus, Pencil, Trash2, Eye, EyeOff, Copy, Check,
  X, Loader2, ShieldCheck, Server, Box, Database, Key, FileKey2,
  Lock, AlertTriangle, RefreshCcw,
} from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/ui/metric-card";
import { cn, formatDate } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import type { SecretMeta, SecretStats } from "@opspilot/shared-types";

// ── Constants ───────────────────────────────────────────────

const TYPE_LABELS: Record<string, string> = {
  vcenter: "vCenter 凭据",
  kubeconfig: "Kubernetes 凭据",
  api_key: "API Key",
  database: "数据库凭据",
  ssh_key: "SSH 密钥",
  certificate: "证书",
  generic: "通用密钥",
};

const TYPE_ICONS: Record<string, typeof KeyRound> = {
  vcenter: Server,
  kubeconfig: Box,
  api_key: Key,
  database: Database,
  ssh_key: FileKey2,
  certificate: ShieldCheck,
  generic: Lock,
};

const TYPE_COLORS: Record<string, string> = {
  vcenter: "bg-blue-50 text-blue-700",
  kubeconfig: "bg-violet-50 text-violet-700",
  api_key: "bg-amber-50 text-amber-700",
  database: "bg-emerald-50 text-emerald-700",
  ssh_key: "bg-slate-100 text-slate-700",
  certificate: "bg-teal-50 text-teal-700",
  generic: "bg-slate-100 text-slate-600",
};

const SECRET_TEMPLATES: Record<string, { hint: string; placeholder: string }> = {
  vcenter: {
    hint: "JSON 格式: {\"username\": \"...\", \"password\": \"...\"}",
    placeholder: '{"username": "administrator@vsphere.local", "password": "P@ssw0rd!"}',
  },
  kubeconfig: {
    hint: "JSON 格式: {\"kubeconfig\": \"...\"}，或直接粘贴 kubeconfig 内容",
    placeholder: '{"kubeconfig": "apiVersion: v1\\nkind: Config\\n..."}',
  },
  api_key: {
    hint: "JSON 格式: {\"api_key\": \"...\"}",
    placeholder: '{"api_key": "sk-xxxxxxxxxxxx"}',
  },
  database: {
    hint: "JSON 格式: {\"host\": \"...\", \"port\": ..., \"username\": \"...\", \"password\": \"...\", \"database\": \"...\"}",
    placeholder: '{"host": "db.corp.local", "port": 3306, "username": "root", "password": "***", "database": "opspilot"}',
  },
  ssh_key: {
    hint: "JSON 格式: {\"private_key\": \"...\", \"passphrase\": \"...\"}",
    placeholder: '{"private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\\n...", "passphrase": ""}',
  },
  certificate: {
    hint: "JSON 格式: {\"cert\": \"...\", \"key\": \"...\", \"ca\": \"...\"}",
    placeholder: '{"cert": "-----BEGIN CERTIFICATE-----\\n...", "key": "...", "ca": "..."}',
  },
  generic: {
    hint: "任意文本或 JSON",
    placeholder: '{"value": "my-secret-value"}',
  },
};

// ── Main Component ──────────────────────────────────────────

export default function SecretManagementPage() {
  const [secrets, setSecrets] = useState<SecretMeta[]>([]);
  const [stats, setStats] = useState<SecretStats>({ total: 0, by_type: {} });
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("");

  const [selected, setSelected] = useState<SecretMeta | null>(null);
  const [revealedValue, setRevealedValue] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [copied, setCopied] = useState(false);

  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "", display_name: "", secret_type: "generic", value: "", description: "", tags: "",
  });
  const [creating, setCreating] = useState(false);

  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({
    display_name: "", value: "", description: "", tags: "",
  });
  const [saving, setSaving] = useState(false);

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const fetchAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<{ data: SecretMeta[] }>("/api/v1/secrets").then(r => setSecrets(r.data ?? [])),
      apiFetch<{ data: SecretStats }>("/api/v1/secrets/stats").then(r => setStats(r.data ?? { total: 0, by_type: {} })),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  function selectSecret(s: SecretMeta) {
    setSelected(s);
    setRevealedValue(null);
    setCopied(false);
  }

  async function handleReveal() {
    if (!selected) return;
    setRevealing(true);
    try {
      const r = await apiFetch<{ data: { name: string; value: string } }>(`/api/v1/secrets/${selected.name}/reveal`, {
        method: "POST", body: JSON.stringify({ confirm: true }),
      });
      setRevealedValue(r.data?.value ?? null);
    } finally { setRevealing(false); }
  }

  function handleCopy() {
    if (!revealedValue) return;
    navigator.clipboard.writeText(revealedValue);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleCreate() {
    setCreating(true);
    try {
      await apiFetch("/api/v1/secrets", {
        method: "POST",
        body: JSON.stringify({
          ...createForm,
          tags: createForm.tags.split(",").map(t => t.trim()).filter(Boolean),
        }),
      });
      setShowCreate(false);
      setCreateForm({ name: "", display_name: "", secret_type: "generic", value: "", description: "", tags: "" });
      fetchAll();
    } finally { setCreating(false); }
  }

  function openEdit(s: SecretMeta) {
    setEditForm({
      display_name: s.display_name,
      value: "",
      description: s.description,
      tags: s.tags.join(", "),
    });
    setShowEdit(true);
  }

  async function handleEdit() {
    if (!selected) return;
    setSaving(true);
    try {
      const body: Record<string, unknown> = {
        display_name: editForm.display_name,
        description: editForm.description,
        tags: editForm.tags.split(",").map(t => t.trim()).filter(Boolean),
      };
      if (editForm.value) body.value = editForm.value;
      await apiFetch(`/api/v1/secrets/${selected.name}`, {
        method: "PUT", body: JSON.stringify(body),
      });
      setShowEdit(false);
      setRevealedValue(null);
      const res = await apiFetch<{ data: SecretMeta[] }>("/api/v1/secrets");
      setSecrets(res.data ?? []);
      setSelected(res.data?.find(s => s.name === selected.name) ?? null);
    } finally { setSaving(false); }
  }

  async function handleDelete() {
    if (!selected) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/secrets/${selected.name}`, { method: "DELETE" });
      setShowDeleteConfirm(false);
      setSelected(null);
      fetchAll();
    } finally { setDeleting(false); }
  }

  const filtered = secrets.filter(s => {
    if (searchQuery && !s.name.includes(searchQuery) && !s.display_name.includes(searchQuery)) return false;
    if (filterType && s.secret_type !== filterType) return false;
    return true;
  });

  const types = [...new Set(secrets.map(s => s.secret_type))];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="密钥管理"
        description="AES-256-GCM 加密存储 · 凭据全生命周期管理"
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={fetchAll}><RefreshCcw className="h-3.5 w-3.5" /> 刷新</Button>
            <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}><Plus className="h-3.5 w-3.5" /> 新建密钥</Button>
          </div>
        }
      />

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard title="密钥总数" value={stats.total} icon={KeyRound} accent="blue" />
        <MetricCard title="vCenter 凭据" value={stats.by_type.vcenter ?? 0} icon={Server} accent="purple" />
        <MetricCard title="API Key" value={stats.by_type.api_key ?? 0} icon={Key} accent="amber" />
        <MetricCard title="其他类型" value={stats.total - (stats.by_type.vcenter ?? 0) - (stats.by_type.api_key ?? 0)} icon={Lock} accent="green" />
      </div>

      {/* Main Area */}
      <div className="grid grid-cols-[320px_1fr] gap-4 min-h-[500px]">
        {/* Left: List */}
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                className="h-8 w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                placeholder="搜索密钥..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
            <select className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-xs outline-none" value={filterType} onChange={e => setFilterType(e.target.value)}>
              <option value="">全部类型</option>
              {types.map(t => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
            </select>
          </div>

          <div className="space-y-1 max-h-[calc(100vh-340px)] overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="text-center py-12">
                <KeyRound className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                <p className="text-xs text-slate-400">{secrets.length === 0 ? "尚未创建任何密钥" : "无匹配结果"}</p>
              </div>
            ) : filtered.map(s => {
              const Icon = TYPE_ICONS[s.secret_type] ?? Lock;
              const active = selected?.name === s.name;
              return (
                <button
                  key={s.name}
                  onClick={() => selectSecret(s)}
                  className={cn(
                    "w-full text-left rounded-lg border px-3 py-2.5 transition-all",
                    active ? "border-blue-300 bg-blue-50/60 shadow-sm" : "border-slate-100 bg-white hover:border-slate-200 hover:bg-slate-50/50"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", TYPE_COLORS[s.secret_type] ?? TYPE_COLORS.generic)}>
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-slate-800 truncate">{s.display_name}</p>
                      <p className="text-[10px] text-slate-400 font-mono truncate">{s.name}</p>
                    </div>
                    <Badge variant="neutral" className="text-[9px] shrink-0">{TYPE_LABELS[s.secret_type] ?? s.secret_type}</Badge>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Detail */}
        <div className="space-y-3">
          {selected ? (
            <>
              {/* Info Card */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      {(() => { const I = TYPE_ICONS[selected.secret_type] ?? Lock; return <I className="h-4 w-4 text-slate-400" />; })()}
                      {selected.display_name}
                    </CardTitle>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="xs" onClick={() => openEdit(selected)}><Pencil className="h-3 w-3" /></Button>
                      <Button variant="ghost" size="xs" className="text-red-500 hover:text-red-600 hover:bg-red-50" onClick={() => setShowDeleteConfirm(true)}><Trash2 className="h-3 w-3" /></Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                    <InfoCell label="名称" value={selected.name} mono />
                    <InfoCell label="类型" value={TYPE_LABELS[selected.secret_type] ?? selected.secret_type} />
                    <InfoCell label="创建时间" value={formatDate(selected.created_at)} />
                    <InfoCell label="更新时间" value={formatDate(selected.updated_at)} />
                  </div>
                  {selected.description && (
                    <div>
                      <p className="text-[10px] text-slate-400 mb-0.5">描述</p>
                      <p className="text-xs text-slate-600">{selected.description}</p>
                    </div>
                  )}
                  {selected.tags.length > 0 && (
                    <div>
                      <p className="text-[10px] text-slate-400 mb-1">标签</p>
                      <div className="flex flex-wrap gap-1">
                        {selected.tags.map(t => <Badge key={t} variant="neutral" className="text-[9px]">{t}</Badge>)}
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="text-[10px] text-slate-400 mb-0.5">凭据引用</p>
                    <p className="text-xs font-mono text-blue-600 bg-blue-50/50 rounded-md px-2 py-1 inline-block">secret://{selected.name}</p>
                  </div>
                </CardContent>
              </Card>

              {/* Reveal Card */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5"><Eye className="h-3.5 w-3.5 text-slate-400" />密钥值</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-2.5">
                    <p className="text-[10px] text-amber-700 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      解密后的密钥值将在页面上明文显示，请确保当前环境安全
                    </p>
                  </div>

                  {revealedValue !== null ? (
                    <div className="space-y-2">
                      <div className="relative">
                        <pre className="rounded-lg border border-slate-200 bg-slate-900 text-slate-100 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap max-h-[200px]">
                          {formatRevealedValue(revealedValue)}
                        </pre>
                        <div className="absolute top-2 right-2 flex gap-1">
                          <button onClick={handleCopy} className="rounded-md bg-slate-700 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-600 transition-colors">
                            {copied ? <><Check className="h-3 w-3 inline" /> 已复制</> : <><Copy className="h-3 w-3 inline" /> 复制</>}
                          </button>
                        </div>
                      </div>
                      <Button variant="ghost" size="xs" onClick={() => setRevealedValue(null)}>
                        <EyeOff className="h-3 w-3" /> 隐藏
                      </Button>
                    </div>
                  ) : (
                    <Button variant="secondary" size="sm" onClick={handleReveal} disabled={revealing}>
                      {revealing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />}
                      解密并显示
                    </Button>
                  )}
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <KeyRound className="h-10 w-10 text-slate-200 mb-3" />
              <p className="text-sm text-slate-400">选择一个密钥查看详情</p>
              <p className="text-[10px] text-slate-300 mt-1">所有密钥均以 AES-256-GCM 加密存储于本地数据库</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Create Dialog ──────────── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowCreate(false)}>
          <div className="w-[580px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">新建密钥</h2>
              <button onClick={() => setShowCreate(false)} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-4 space-y-3 max-h-[65vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-3">
                <FormField label="密钥名称" hint="唯一标识，用于 secret:// 引用">
                  <input className="form-input" value={createForm.name} onChange={e => setCreateForm(p => ({ ...p, name: e.target.value }))} placeholder="vcenter-prod" />
                </FormField>
                <FormField label="显示名称">
                  <input className="form-input" value={createForm.display_name} onChange={e => setCreateForm(p => ({ ...p, display_name: e.target.value }))} placeholder="vCenter 生产环境凭据" />
                </FormField>
              </div>
              <FormField label="密钥类型">
                <select className="form-input" value={createForm.secret_type} onChange={e => setCreateForm(p => ({ ...p, secret_type: e.target.value }))}>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </FormField>
              <FormField label="密钥值" hint={SECRET_TEMPLATES[createForm.secret_type]?.hint ?? "任意文本或 JSON"}>
                <textarea
                  className="form-input min-h-[80px] font-mono text-[12px]"
                  value={createForm.value}
                  onChange={e => setCreateForm(p => ({ ...p, value: e.target.value }))}
                  placeholder={SECRET_TEMPLATES[createForm.secret_type]?.placeholder ?? ""}
                />
              </FormField>
              <FormField label="描述">
                <input className="form-input" value={createForm.description} onChange={e => setCreateForm(p => ({ ...p, description: e.target.value }))} placeholder="用途说明" />
              </FormField>
              <FormField label="标签" hint="逗号分隔">
                <input className="form-input" value={createForm.tags} onChange={e => setCreateForm(p => ({ ...p, tags: e.target.value }))} placeholder="production, vcenter" />
              </FormField>

              <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-2.5 text-[10px] text-blue-700 flex items-start gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">加密存储说明</p>
                  <p className="mt-0.5 text-blue-600/80">密钥值将使用 AES-256-GCM 加密后存入本地 SQLite 数据库。加密密钥通过 PBKDF2 从主密码派生，每条记录使用独立的 Salt 和 IV。创建后，连接配置中可使用 <code className="font-mono bg-blue-100 px-1 rounded">secret://{createForm.name || "<name>"}</code> 引用此密钥。</p>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowCreate(false)}>取消</Button>
              <Button variant="primary" size="sm" onClick={handleCreate} disabled={creating || !createForm.name || !createForm.value}>
                {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} 创建
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Dialog ──────────── */}
      {showEdit && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowEdit(false)}>
          <div className="w-[560px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
              <h2 className="text-sm font-semibold text-slate-900">编辑密钥 — {selected.display_name}</h2>
              <button onClick={() => setShowEdit(false)} className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
              <FormField label="显示名称">
                <input className="form-input" value={editForm.display_name} onChange={e => setEditForm(p => ({ ...p, display_name: e.target.value }))} />
              </FormField>
              <FormField label="新密钥值" hint="留空表示不更新密钥值">
                <textarea
                  className="form-input min-h-[80px] font-mono text-[12px]"
                  value={editForm.value}
                  onChange={e => setEditForm(p => ({ ...p, value: e.target.value }))}
                  placeholder="输入新的密钥值（留空则保持原值不变）"
                />
              </FormField>
              <FormField label="描述">
                <input className="form-input" value={editForm.description} onChange={e => setEditForm(p => ({ ...p, description: e.target.value }))} />
              </FormField>
              <FormField label="标签" hint="逗号分隔">
                <input className="form-input" value={editForm.tags} onChange={e => setEditForm(p => ({ ...p, tags: e.target.value }))} />
              </FormField>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowEdit(false)}>取消</Button>
              <Button variant="primary" size="sm" onClick={handleEdit} disabled={saving || !editForm.display_name}>
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Pencil className="h-3.5 w-3.5" />} 保存
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirm Dialog ── */}
      {showDeleteConfirm && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowDeleteConfirm(false)}>
          <div className="w-[420px] bg-white rounded-xl shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-5 text-center">
              <div className="mx-auto w-10 h-10 rounded-full bg-red-50 flex items-center justify-center mb-3">
                <Trash2 className="h-5 w-5 text-red-500" />
              </div>
              <h3 className="text-sm font-semibold text-slate-900 mb-1">确认删除密钥</h3>
              <p className="text-xs text-slate-500 mb-1">即将删除密钥 <span className="font-medium text-slate-700">{selected.display_name}</span></p>
              <p className="text-xs text-amber-600 mb-1"><AlertTriangle className="h-3 w-3 inline mr-0.5" />引用 <code className="font-mono text-[10px] bg-amber-50 px-1 rounded">secret://{selected.name}</code> 的连接将无法自动获取凭据</p>
              <p className="text-[11px] text-slate-400">此操作不可恢复，加密数据将被永久删除</p>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-slate-100">
              <Button variant="secondary" size="sm" onClick={() => setShowDeleteConfirm(false)}>取消</Button>
              <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
                {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} 确认删除
              </Button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .form-input { display:block; width:100%; height:32px; padding:0 10px; border:1px solid #e2e8f0; border-radius:8px; font-size:13px; color:#1e293b; background:#fff; outline:none; transition:border-color 150ms,box-shadow 150ms; }
        .form-input:focus { border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.15); }
        textarea.form-input { height:auto; padding:8px 10px; resize:vertical; }
        select.form-input { appearance:auto; }
      `}</style>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────

function InfoCell({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-[10px] text-slate-400 mb-0.5">{label}</p>
      <p className={cn("text-xs text-slate-700", mono && "font-mono")}>{value || "—"}</p>
    </div>
  );
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[11px] font-medium text-slate-600 mb-1 block">
        {label}
        {hint && <span className="text-[10px] text-slate-400 font-normal ml-1">({hint})</span>}
      </label>
      {children}
    </div>
  );
}

function formatRevealedValue(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}
