import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LLMSettingsUpdatePayload } from '@/entities/LLMSettings';
import { llmSettingsApi } from './api';

export const llmSettingsKeys = {
  all: ['llm-settings'] as const,
};

export function useLLMSettings() {
  return useQuery({
    queryKey: llmSettingsKeys.all,
    queryFn: () => llmSettingsApi.get(),
  });
}

export function useUpdateLLMSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LLMSettingsUpdatePayload) => llmSettingsApi.update(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: llmSettingsKeys.all }),
  });
}
