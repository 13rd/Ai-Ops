import type { APIResponse } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';
import type { ContainerSnapshot } from '@/entities/Container';

export const containersApi = {
  list: async (serverId: number): Promise<ContainerSnapshot[]> =>
    unwrap(await apiClient.get<APIResponse<ContainerSnapshot[]>>(`/servers/${serverId}/containers`)),

  action: async (
    serverId: number,
    containerId: string,
    action: 'start' | 'stop' | 'restart',
  ): Promise<{ server_id: number; container_id: string; action: string }> =>
    unwrap(
      await apiClient.post<APIResponse<{ server_id: number; container_id: string; action: string }>>(
        `/servers/${serverId}/containers/${containerId}/${action}`,
      ),
    ),

  remove: async (
    serverId: number,
    containerId: string,
    force = false,
  ): Promise<{ server_id: number; container_id: string; action: string }> =>
    unwrap(
      await apiClient.delete<APIResponse<{ server_id: number; container_id: string; action: string }>>(
        `/servers/${serverId}/containers/${containerId}`,
        { params: { force } },
      ),
    ),

  logs: async (
    serverId: number,
    containerId: string,
    tail = 100,
    timestamps = false,
  ): Promise<{ lines: string[] }> =>
    unwrap(
      await apiClient.get<APIResponse<{ lines: string[] }>>(
        `/servers/${serverId}/containers/${containerId}/logs`,
        { params: { tail, timestamps } },
      ),
    ),
};
