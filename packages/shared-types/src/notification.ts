export type NotificationStatus = "pending" | "delivered" | "acknowledged" | "escalated" | "timed_out";
export type NotificationChannel = "dingtalk" | "wecom" | "email" | "sms" | "webhook" | "phone";
export type NotificationPriority = "low" | "normal" | "high" | "urgent";

export interface NotificationItem {
  id: string;
  title: string;
  content: string;
  priority: NotificationPriority;
  status: NotificationStatus;
  incident_ref: string | null;
  channels: NotificationChannel[];
  recipients: string[];
  created_at: string;
  delivered_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  escalation_count: number;
  next_escalation_at: string | null;
}

export interface OnCallShift {
  id: string;
  name: string;
  team: string;
  members: string[];
  start_at: string;
  end_at: string;
  active: boolean;
}
