import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UserCreatePayload, UserUpdatePayload } from '@/entities/User';
import { usersApi } from './api';

export const userKeys = {
  all: ['users'] as const,
  list: (limit: number, offset: number) => ['users', 'list', limit, offset] as const,
  detail: (id: number) => ['users', 'detail', id] as const,
  servers: (id: number) => ['users', id, 'servers'] as const,
};

export function useUsers(limit = 100, offset = 0) {
  return useQuery({
    queryKey: userKeys.list(limit, offset),
    queryFn: () => usersApi.list(limit, offset),
  });
}

export function useUser(id: number) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => usersApi.get(id),
    enabled: id > 0,
  });
}

export function useUserServers(id: number) {
  return useQuery({
    queryKey: userKeys.servers(id),
    queryFn: () => usersApi.getServers(id),
    enabled: id > 0,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserCreatePayload) => usersApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useUpdateUser(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserUpdatePayload) => usersApi.update(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => usersApi.deactivate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.all }),
  });
}

export function useSetUserServers(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (accesses: { server_id: number; permission: string }[]) =>
      usersApi.setServers(userId, accesses),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.servers(userId) }),
  });
}
