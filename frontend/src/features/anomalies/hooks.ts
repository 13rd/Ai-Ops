import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { AnomalyFilters } from '@/entities/Anomaly';
import { anomaliesApi } from './api';

export const anomalyKeys = {
  all: ['anomalies'] as const,
  list: (filters: AnomalyFilters) => ['anomalies', 'list', filters] as const,
  detail: (id: number) => ['anomalies', 'detail', id] as const,
  recommendations: (anomalyId: number) => ['anomalies', anomalyId, 'recommendations'] as const,
};

export function useAnomalies(filters: AnomalyFilters = {}) {
  return useQuery({
    queryKey: anomalyKeys.list(filters),
    queryFn: () => anomaliesApi.list(filters),
    refetchInterval: 30_000,
  });
}

export function useAnomaly(id: number) {
  return useQuery({
    queryKey: anomalyKeys.detail(id),
    queryFn: () => anomaliesApi.get(id),
    enabled: id > 0,
  });
}

export function useAnomalyRecommendations(anomalyId: number) {
  return useQuery({
    queryKey: anomalyKeys.recommendations(anomalyId),
    queryFn: () => anomaliesApi.listRecommendations(anomalyId),
    enabled: anomalyId > 0,
  });
}

export function useUpdateAnomalyStatus(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (status: string) => anomaliesApi.updateStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: anomalyKeys.detail(id) });
      qc.invalidateQueries({ queryKey: anomalyKeys.all });
    },
  });
}

export function useApproveRecommendation(anomalyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (recId: number) => anomaliesApi.approveRecommendation(recId),
    onSuccess: () => qc.invalidateQueries({ queryKey: anomalyKeys.recommendations(anomalyId) }),
  });
}

export function useRejectRecommendation(anomalyId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (recId: number) => anomaliesApi.rejectRecommendation(recId),
    onSuccess: () => qc.invalidateQueries({ queryKey: anomalyKeys.recommendations(anomalyId) }),
  });
}
