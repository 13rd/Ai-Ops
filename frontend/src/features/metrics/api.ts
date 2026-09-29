import apiClient from '@/shared/api/client';
import { unwrap, type APIResponse } from '@/shared/api/types';
import type {
  AggregationLevel,
  AvailableAggregations,
  HistoricalMetricsData,
  MetricSnapshot,
  MetricTypeName,
  TimeRange,
} from '@/entities/Metric';

export const metricsApi = {
  latest: async (serverId: number): Promise<MetricSnapshot | null> =>
    unwrap(await apiClient.get<APIResponse<MetricSnapshot | null>>(
      `/servers/${serverId}/metrics/latest`,
    )),

  history: async (serverId: number, limit = 100): Promise<MetricSnapshot[]> =>
    unwrap(await apiClient.get<APIResponse<MetricSnapshot[]>>(
      `/servers/${serverId}/metrics/history`,
      { params: { limit } },
    )),

  historical: async (
    serverId: number,
    metricType: MetricTypeName,
    timeRange: TimeRange,
    aggregationLevel: AggregationLevel,
  ): Promise<HistoricalMetricsData> =>
    unwrap(await apiClient.get<APIResponse<HistoricalMetricsData>>(
      `/servers/${serverId}/metrics/historical/${metricType}`,
      { params: { time_range: timeRange, aggregation_level: aggregationLevel } },
    )),

  availableAggregations: async (
    serverId: number,
    metricType: MetricTypeName,
  ): Promise<AvailableAggregations> =>
    unwrap(await apiClient.get<APIResponse<AvailableAggregations>>(
      `/servers/${serverId}/metrics/available-aggregations`,
      { params: { metric_type: metricType } },
    )),
};
