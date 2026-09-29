import { useQuery } from '@tanstack/react-query';
import type { AggregationLevel, MetricTypeName, TimeRange } from '@/entities/Metric';
import { DEFAULT_AGG } from '@/entities/Metric';
import { metricsApi } from './api';

export const metricKeys = {
  latest: (serverId: number) => ['metrics', serverId, 'latest'] as const,
  history: (serverId: number, limit: number) => ['metrics', serverId, 'history', limit] as const,
  historical: (
    serverId: number,
    type: MetricTypeName,
    range: TimeRange,
    agg: AggregationLevel,
  ) => ['metrics', serverId, 'historical', type, range, agg] as const,
  aggregations: (serverId: number, type: MetricTypeName) =>
    ['metrics', serverId, 'aggregations', type] as const,
};

export function useLatestMetrics(serverId: number) {
  return useQuery({
    queryKey: metricKeys.latest(serverId),
    queryFn: () => metricsApi.latest(serverId),
    refetchInterval: 15_000,
    enabled: serverId > 0,
  });
}

export function useMetricHistory(serverId: number, limit = 100) {
  return useQuery({
    queryKey: metricKeys.history(serverId, limit),
    queryFn: () => metricsApi.history(serverId, limit),
    refetchInterval: 15_000,
    enabled: serverId > 0,
  });
}

export function useHistoricalMetric(
  serverId: number,
  metricType: MetricTypeName,
  timeRange: TimeRange,
  aggregationLevel?: AggregationLevel,
) {
  const agg = aggregationLevel ?? DEFAULT_AGG[timeRange];
  return useQuery({
    queryKey: metricKeys.historical(serverId, metricType, timeRange, agg),
    queryFn: () => metricsApi.historical(serverId, metricType, timeRange, agg),
    enabled: serverId > 0,
    staleTime: 60_000,
  });
}

export function useAvailableAggregations(serverId: number, metricType: MetricTypeName) {
  return useQuery({
    queryKey: metricKeys.aggregations(serverId, metricType),
    queryFn: () => metricsApi.availableAggregations(serverId, metricType),
    enabled: serverId > 0,
    staleTime: 300_000,
  });
}
