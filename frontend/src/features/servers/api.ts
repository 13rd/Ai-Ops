import apiClient from '@/shared/api/client';
import { unwrap, type APIResponse, type PaginatedData } from '@/shared/api/types';
import type {
  ConnectionTestResult,
  MyServerAccess,
  Server,
  ServerCreatePayload,
  ServerFilters,
  ServerPermissionResult,
  ServerUpdatePayload,
} from '@/entities/Server';

export const serversApi = {
  list: async (filters: ServerFilters = {}): Promise<PaginatedData<Server>> =>
    unwrap(await apiClient.get<APIResponse<PaginatedData<Server>>>('/servers', { params: filters })),

  get: async (id: number): Promise<Server> =>
    unwrap(await apiClient.get<APIResponse<Server>>(`/servers/${id}`)),

  create: async (data: ServerCreatePayload): Promise<Server> =>
    unwrap(await apiClient.post<APIResponse<Server>>('/servers', data)),

  update: async (id: number, data: ServerUpdatePayload): Promise<Server> =>
    unwrap(await apiClient.put<APIResponse<Server>>(`/servers/${id}`, data)),

  delete: async (id: number): Promise<{ server_id: number }> =>
    unwrap(await apiClient.delete<APIResponse<{ server_id: number }>>(`/servers/${id}`)),

  testConnection: async (id: number): Promise<ConnectionTestResult> =>
    unwrap(await apiClient.post<APIResponse<ConnectionTestResult>>(`/connections/test/${id}`)),

  myServers: async (): Promise<MyServerAccess[]> =>
    unwrap(await apiClient.get<APIResponse<MyServerAccess[]>>('/users/me/servers')),

  getMyAccess: async (serverId: number): Promise<ServerPermissionResult> =>
    unwrap(await apiClient.get<APIResponse<ServerPermissionResult>>(`/servers/${serverId}/my-access`)),
};
