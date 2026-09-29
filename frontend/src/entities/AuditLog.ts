export interface AuditLogEntry {
  id: number;
  user_id: number | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditLogFilters {
  user_id?: number;
  action?: string;
  resource_type?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export const AUDIT_ACTIONS = [
  'login',
  'login_failed',
  'logout',
  'token_refreshed',
  'user_created',
  'user_updated',
  'user_deactivated',
  'server_access_assigned',
  'server_created',
  'server_updated',
  'server_deleted',
  'console_opened',
  'console_command',
  'console_closed',
  'container_action',
  'recommendation_approved',
  'recommendation_rejected',
  'anomaly_status_changed',
] as const;

export const AUDIT_RESOURCE_TYPES = [
  'server',
  'user',
  'anomaly',
  'recommendation',
  'container',
  'console',
] as const;
