export type KnowledgeSource = "manual" | "runbook" | "confluence" | "gitlab" | "ai_generated" | "case_derived";
export type KnowledgeStatus = "draft" | "published" | "archived" | "reviewing";

export interface KnowledgeArticle {
  id: string;
  title: string;
  content_summary: string;
  source: KnowledgeSource;
  status: KnowledgeStatus;
  tags: string[];
  categories: string[];
  author: string;
  version: string;
  hit_count: number;
  confidence_score: number;
  created_at: string;
  updated_at: string;
  related_incident_ids: string[];
}

export interface KnowledgeImportJob {
  id: string;
  source_type: KnowledgeSource;
  source_url: string | null;
  status: "queued" | "running" | "completed" | "failed";
  articles_imported: number;
  articles_failed: number;
  started_at: string;
  completed_at: string | null;
  error: string | null;
}
