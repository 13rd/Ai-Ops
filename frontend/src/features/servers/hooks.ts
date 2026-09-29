import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ServerCreatePayload, ServerFilters, ServerUpdatePayload } from '@/entities/Server';
import { serversApi } from './api';

export const serverKeys = {
  all: ['servers'] as const,
  list: (filters: ServerFilters) => ['servers', 'list', filters] as const,
  detail: (id: number) => ['servers', 'detail', id] as const,
  my: ['servers', 'my'] as const,
  myAccess: (serverId: number) => ['servers', 'my-access', serverId] as const,
};

export function useServers(filters: ServerFilters = {}) {
  return useQuery({
    queryKey: serverKeys.list(filters),
    queryFn: () => serversApi.list(filters),
  });
}

export function useServer(id: number | undefined) {
  return useQuery({
    queryKey: serverKeys.detail(id!),
    queryFn: () => serversApi.get(id!),
    enabled: id !== undefined,
  });
}

export function useMyServers() {
  return useQuery({
    queryKey: serverKeys.my,
    queryFn: serversApi.myServers,
  });
}

export function useMyServerAccess(serverId: number) {
  return useQuery({
    queryKey: serverKeys.myAccess(serverId),
    queryFn: () => serversApi.getMyAccess(serverId),
    enabled: serverId > 0,
  });
}

export function useCreateServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ServerCreatePayload) => serversApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: serverKeys.all }),
  });
}

export function useUpdateServer(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ServerUpdatePayload) => serversApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: serverKeys.all }),
  });
}

export function useDeleteServer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => serversApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: serverKeys.all }),
  });
}

export function useTestConnection(id: number) {
  return useMutation({
    mutationFn: () => serversApi.testConnection(id),
  });
}
