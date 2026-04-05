export interface ApiEnvelope<T = unknown> {
  request_id: string;
  success: boolean;
  message: string;
  data: T | null;
  error: string | null;
  audit_ref: string | null;
  trace_id: string;
  timestamp: string;
}
