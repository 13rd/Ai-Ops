export type AnomalyType =
  | 'memory_leak'
  | 'cpu_spike'
  | 'container_crash'
  | 'service_down'
  | 'disk_pressure'
  | 'network_anomaly'
  | 'disk_fill'
  | 'network_storm';

export type AnomalySeverity = 'low' | 'medium' | 'high' | 'critical';
export type AnomalyStatus = 'open' | 'investigating' | 'resolved';

export interface ShapImpact {
  metric: string;
  impact_percent: number;
  ae_contribution?: number | null;
  shap_contribution?: number | null;
}

export interface Anomaly {
  id: number;
  server_id: number;
  detected_at: string;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  reconstruction_error: number;
  threshold: number;
  shap_explanation: Record<string, number> | ShapImpact[];
  metrics_snapshot: Record<string, unknown>;
  status: AnomalyStatus;
  resolved_at: string | null;
  resolved_by: number | null;
}

export interface AnomalyFilters {
  server_id?: number;
  type?: string;
  severity?: string;
  status?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export const ANOMALY_TYPES: AnomalyType[] = [
  'cpu_spike',
  'memory_leak',
  'disk_pressure',
  'network_anomaly',
  'container_crash',
  'service_down',
];

export const ANOMALY_SEVERITIES: AnomalySeverity[] = ['low', 'medium', 'high', 'critical'];
export const ANOMALY_STATUSES: AnomalyStatus[] = ['open', 'investigating', 'resolved'];
