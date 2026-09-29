export type NotificationSeverity = 'low' | 'medium' | 'high' | 'critical';

export interface AppNotification {
  id: number;
  user_id: number;
  anomaly_id: number | null;
  title: string;
  body: string;
  severity: NotificationSeverity;
  is_read: boolean;
  read_at: string | null;
  sent_at: string;
  channels_sent: string[];
}

export interface NotificationChannel {
  id: number;
  user_id: number;
  channel_type: 'inapp' | 'telegram';
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationFilters {
  is_read?: boolean;
  limit?: number;
  offset?: number;
}
