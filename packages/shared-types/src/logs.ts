export type LogBackendType = "opensearch" | "loki" | "graylog" | "elastic";
export type LogAuthType = "none" | "basic" | "token";

export interface LogExternalLink {
  provider: string;
  title: string;
  url: string;
  query?: string | null;
  kind?: string;
}

export interface LogSourceConfig {
  id: string;
  name: string;
  backend_type: LogBackendType;
  endpoint: string;
  auth_type: LogAuthType;
  username?: string | null;
  index_pattern: string;
  tenant?: string | null;
  tls_verify: boolean;
  default_time_window: number;
  max_result_limit: number;
  enabled: boolean;
  web_url?: string | null;
  has_secret?: boolean;
}

export interface LogItem {
  log_id: string;
  timestamp: string;
  source: string;
  product?: string | null;
  component?: string | null;
  severity?: string | null;
  message: string;
  raw_message: string;
  fields: Record<string, unknown>;
  backend: LogBackendType;
  index?: string | null;
  document_id?: string | null;
  external_links?: LogExternalLink[];
}

export interface LogSearchResponse {
  total: number;
  items: LogItem[];
  backend?: LogBackendType | null;
  source_id?: string | null;
  queries_executed?: string[];
}

export interface LogContextGroup {
  name: string;
  count: number;
  items: LogItem[];
}

export interface LogContextResponse {
  incident_id?: string | null;
  queries_executed: string[];
  groups: LogContextGroup[];
}
