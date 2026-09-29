import type { APIResponse, PaginatedData } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';
import type { Anomaly, AnomalyFilters } from '@/entities/Anomaly';
import type { Recommendation } from '@/entities/Recommendation';

export const anomaliesApi = {
  list: async (filters: AnomalyFilters = {}): Promise<PaginatedData<Anomaly>> =>
    unwrap(
      await apiClient.get<APIResponse<PaginatedData<Anomaly>>>('/anomalies', { params: filters }),
    ),

  get: async (id: number): Promise<Anomaly> =>
    unwrap(await apiClient.get<APIResponse<Anomaly>>(`/anomalies/${id}`)),

  updateStatus: async (id: number, status: string): Promise<Anomaly> =>
    unwrap(
      await apiClient.patch<APIResponse<Anomaly>>(`/anomalies/${id}/status`, { status }),
    ),

  listRecommendations: async (anomalyId: number): Promise<Recommendation[]> =>
    unwrap(
      await apiClient.get<APIResponse<Recommendation[]>>(
        `/anomalies/${anomalyId}/recommendations`,
      ),
    ),

  approveRecommendation: async (recId: number): Promise<Recommendation> =>
    unwrap(
      await apiClient.post<APIResponse<Recommendation>>(`/recommendations/${recId}/approve`),
    ),

  rejectRecommendation: async (recId: number): Promise<Recommendation> =>
    unwrap(
      await apiClient.post<APIResponse<Recommendation>>(`/recommendations/${recId}/reject`),
    ),
};
