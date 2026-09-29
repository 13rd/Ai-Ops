import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { NotificationFilters } from '@/entities/Notification';
import { notificationsApi } from './api';

export const notificationKeys = {
  all: ['notifications'] as const,
  list: (filters: NotificationFilters) => ['notifications', 'list', filters] as const,
  unread: ['notifications', 'unread'] as const,
  channels: ['notifications', 'channels'] as const,
};

export function useNotifications(filters: NotificationFilters = {}) {
  return useQuery({
    queryKey: notificationKeys.list(filters),
    queryFn: () => notificationsApi.list(filters),
    refetchInterval: 30_000,
  });
}

export function useUnreadNotifications() {
  return useQuery({
    queryKey: notificationKeys.unread,
    queryFn: () => notificationsApi.list({ is_read: false, limit: 10 }),
    refetchInterval: 30_000,
  });
}

export function useMarkAsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

export function useNotificationChannels() {
  return useQuery({
    queryKey: notificationKeys.channels,
    queryFn: notificationsApi.listChannels,
  });
}

export function useUpsertChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      channel_type,
      config,
      enabled,
    }: {
      channel_type: string;
      config: Record<string, unknown>;
      enabled: boolean;
    }) => notificationsApi.upsertChannel(channel_type, config, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.channels }),
  });
}

export function useUpdateChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: { config?: Record<string, unknown>; enabled?: boolean };
    }) => notificationsApi.updateChannel(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.channels }),
  });
}

export function useDeleteChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => notificationsApi.deleteChannel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.channels }),
  });
}
