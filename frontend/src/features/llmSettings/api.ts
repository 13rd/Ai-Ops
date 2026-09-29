import type { LLMSettings, LLMSettingsUpdatePayload } from '@/entities/LLMSettings';
import type { APIResponse } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';

export const llmSettingsApi = {
  get: async (): Promise<LLMSettings> =>
    unwrap(await apiClient.get<APIResponse<LLMSettings>>('/llm-settings')),

  update: async (payload: LLMSettingsUpdatePayload): Promise<LLMSettings> =>
    unwrap(await apiClient.put<APIResponse<LLMSettings>>('/llm-settings', payload)),
};
