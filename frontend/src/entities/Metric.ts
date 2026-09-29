export type MetricTypeName =
  | 'cpu_percent'
  | 'memory_percent'
  | 'disk_percent'
  | 'network_in'
  | 'network_out'
  | 'load_average_1m'
  | 'disk_read'
  | 'disk_write';

export type TimeRange = '1h' | '24h' | '7d' | '30d';
export type AggregationLevel = 'minute' | 'hour' | 'day';

export interface MetricSnapshot {
  id: number;
  server_id: number;
  collected_at: string;
  cpu_usage_percent: number | null;
  memory_usage_percent: number | null;
  disk_usage_percent: number | null;
  network_in_bytes: number | null;
  network_out_bytes: number | null;
  load_average_1m: number | null;
  memory_total_mb: number | null;
  memory_used_mb: number | null;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
}

export interface HistoricalMetricPoint {
  id: number;
  server_id: number;
  metric_type: string;
  aggregation_level: string;
  timestamp: string;
  period_start: string;
  value_min: number | null;
  value_max: number | null;
  value_avg: number | null;
  value_last: number | null;
  sample_count: number;
  collected_at: string;
}

export interface HistoricalMetricsData {
  server_id: number;
  metric_type: string;
  time_range: string;
  aggregation_level: string;
  metrics: HistoricalMetricPoint[];
}

export interface AvailableAggregations {
  metric_type: string;
  available_levels: AggregationLevel[];
}

export const DEFAULT_AGG: Record<TimeRange, AggregationLevel> = {
  '1h': 'minute',
  '24h': 'minute',
  '7d': 'minute',
  '30d': 'minute',
};
