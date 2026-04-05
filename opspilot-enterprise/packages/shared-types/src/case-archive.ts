export type CaseStatus = "open" | "archived" | "reviewing";
export type CaseCategory = "performance" | "availability" | "capacity" | "change_failure" | "security" | "network" | "other";

export interface CaseArchive {
  id: string;
  title: string;
  summary: string;
  category: CaseCategory;
  status: CaseStatus;
  severity: string;
  tags: string[];
  incident_refs: string[];
  root_cause_summary: string;
  resolution_summary: string;
  lessons_learned: string;
  author: string;
  created_at: string;
  archived_at: string | null;
  similarity_score: number | null;
  hit_count: number;
  knowledge_refs: string[];
}
