import type { APIResponse, PaginatedData } from '@/shared/api/types';
import { unwrap } from '@/shared/api/types';
import apiClient from '@/shared/api/client';
import type { AppUser, ServerAccess, UserCreatePayload, UserUpdatePayload } from '@/entities/User';

export const usersApi = {
  list: async (limit = 100, offset = 0): Promise<PaginatedData<AppUser>> =>
    unwrap(
      await apiClient.get<APIResponse<PaginatedData<AppUser>>>('/users', {
        params: { limit, offset },
      }),
    ),

  get: async (id: number): Promise<AppUser> =>
    unwrap(await apiClient.get<APIResponse<AppUser>>(`/users/${id}`)),

  create: async (payload: UserCreatePayload): Promise<AppUser> =>
    unwrap(await apiClient.post<APIResponse<AppUser>>('/users', payload)),

  update: async (id: number, payload: UserUpdatePayload): Promise<AppUser> =>
    unwrap(await apiClient.put<APIResponse<AppUser>>(`/users/${id}`, payload)),

  deactivate: async (id: number): Promise<AppUser> =>
    unwrap(await apiClient.delete<APIResponse<AppUser>>(`/users/${id}`)),

  getServers: async (id: number): Promise<ServerAccess[]> =>
    unwrap(await apiClient.get<APIResponse<ServerAccess[]>>(`/users/${id}/servers`)),

  setServers: async (
    id: number,
    accesses: { server_id: number; permission: string }[],
  ): Promise<ServerAccess[]> =>
    unwrap(
      await apiClient.put<APIResponse<ServerAccess[]>>(`/users/${id}/servers`, { accesses }),
    ),
};
