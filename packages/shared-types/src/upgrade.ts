export type UpgradeStatus = "available" | "downloading" | "ready" | "deploying" | "deployed" | "failed" | "rolled_back";
export type UpgradeTarget = "web-frontend" | "api-bff" | "orchestrator" | "tool-gateway" | "vmware-skill-gateway" | "all-services";

export interface UpgradePackage {
  id: string;
  version: string;
  release_name: string;
  description: string;
  changelog: string[];
  status: UpgradeStatus;
  target: UpgradeTarget;
  package_size_mb: number;
  requires_restart: boolean;
  requires_approval: boolean;
  risk_level: string;
  released_at: string;
  deployed_at: string | null;
  deployed_by: string | null;
  rollback_version: string | null;
  environment: "dev" | "staging" | "production";
}

export interface UpgradeDeploymentRecord {
  id: string;
  package_id: string;
  package_version: string;
  status: UpgradeStatus;
  environment: string;
  deployed_by: string;
  started_at: string;
  completed_at: string | null;
  log_summary: string[];
  rollback_available: boolean;
}
