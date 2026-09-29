export interface LLMSettings {
  id: number;
  enabled: boolean;
  model: string | null;
  timeout_sec: number | null;
  keep_alive: string | null;
  prompt_template: string | null;
  extra: Record<string, unknown>;
  updated_at: string;
  updated_by: number | null;
}

export interface LLMSettingsUpdatePayload {
  enabled?: boolean;
  model?: string | null;
  timeout_sec?: number | null;
  keep_alive?: string | null;
  prompt_template?: string | null;
  extra?: Record<string, unknown>;
}
