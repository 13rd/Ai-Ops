import type { APIResponse, PaginatedData } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';
import type { AuditLogEntry, AuditLogFilters } from '@/entities/AuditLog';

export const auditApi = {
  list: async (filters: AuditLogFilters = {}): Promise<PaginatedData<AuditLogEntry>> =>
    unwrap(
      await apiClient.get<APIResponse<PaginatedData<AuditLogEntry>>>('/audit-log', {
        params: filters,
      }),
    ),
};
