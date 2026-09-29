export interface ContainerSnapshot {
  id: number;
  server_id: number;
  container_id: string;
  container_name: string;
  image: string | null;
  status: string | null;
  cpu_percentage: number | null;
  memory_usage_mb: number | null;
  memory_percentage: number | null;
  restart_count: number | null;
  health_status: string | null;
  ports: string | null;
  command: string | null;
  created_at: string | null;
  started_at: string | null;
  running: boolean | null;
  collected_at: string;
  extra_data: Record<string, unknown>;
}

export type ContainerAction = 'start' | 'stop' | 'restart';
