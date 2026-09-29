import { useQuery } from '@tanstack/react-query';
import type { AuditLogFilters } from '@/entities/AuditLog';
import { auditApi } from './api';

export const auditKeys = {
  list: (filters: AuditLogFilters) => ['audit-log', filters] as const,
};

export function useAuditLog(filters: AuditLogFilters = {}) {
  return useQuery({
    queryKey: auditKeys.list(filters),
    queryFn: () => auditApi.list(filters),
  });
}
