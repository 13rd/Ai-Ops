export type RecommendationStatus = 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';

export interface Recommendation {
  id: number;
  anomaly_id: number;
  llm_raw_output: string | null;
  filtered_command: string;
  explanation: string;
  status: RecommendationStatus;
  approved_by: number | null;
  executed_at: string | null;
  execution_result: Record<string, unknown> | null;
  created_at: string;
}
