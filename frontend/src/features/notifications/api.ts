import type { APIResponse, PaginatedData } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';
import type { AppNotification, NotificationChannel, NotificationFilters } from '@/entities/Notification';

export const notificationsApi = {
  list: async (filters: NotificationFilters = {}): Promise<PaginatedData<AppNotification>> =>
    unwrap(
      await apiClient.get<APIResponse<PaginatedData<AppNotification>>>('/notifications', {
        params: filters,
      }),
    ),

  markRead: async (id: number): Promise<AppNotification> =>
    unwrap(
      await apiClient.post<APIResponse<AppNotification>>(`/notifications/${id}/read`),
    ),

  listChannels: async (): Promise<NotificationChannel[]> =>
    unwrap(
      await apiClient.get<APIResponse<NotificationChannel[]>>('/notifications/channels'),
    ),

  upsertChannel: async (
    channel_type: string,
    config: Record<string, unknown>,
    enabled: boolean,
  ): Promise<NotificationChannel> =>
    unwrap(
      await apiClient.post<APIResponse<NotificationChannel>>('/notifications/channels', {
        channel_type,
        config,
        enabled,
      }),
    ),

  updateChannel: async (
    id: number,
    payload: { config?: Record<string, unknown>; enabled?: boolean },
  ): Promise<NotificationChannel> =>
    unwrap(
      await apiClient.patch<APIResponse<NotificationChannel>>(
        `/notifications/channels/${id}`,
        payload,
      ),
    ),

  deleteChannel: async (id: number): Promise<{ channel_id: number }> =>
    unwrap(
      await apiClient.delete<APIResponse<{ channel_id: number }>>(
        `/notifications/channels/${id}`,
      ),
    ),
};
