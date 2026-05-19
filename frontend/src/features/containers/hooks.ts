import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { containersApi } from './api';

export const containerKeys = {
  list: (serverId: number) => ['containers', serverId] as const,
};

export function useContainers(serverId: number) {
  return useQuery({
    queryKey: containerKeys.list(serverId),
    queryFn: () => containersApi.list(serverId),
    enabled: serverId > 0,
    refetchInterval: 15_000,
  });
}

export function useContainerAction(serverId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      containerId,
      action,
    }: {
      containerId: string;
      action: 'start' | 'stop' | 'restart';
    }) => containersApi.action(serverId, containerId, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: containerKeys.list(serverId) }),
  });
}

export function useDeleteContainer(serverId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ containerId, force }: { containerId: string; force?: boolean }) =>
      containersApi.remove(serverId, containerId, force),
    onSuccess: () => qc.invalidateQueries({ queryKey: containerKeys.list(serverId) }),
  });
}

export function useContainerLogs(
  serverId: number,
  containerId: string | null,
  tail: number,
) {
  return useQuery({
    queryKey: ['container-logs', serverId, containerId, tail],
    queryFn: () => containersApi.logs(serverId, containerId!, tail),
    enabled: !!containerId,
    staleTime: 0,
  });
}

export function useContainerLogStream(
  serverId: number,
  containerId: string,
  tail: number,
  enabled: boolean,
) {
  const [lines, setLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
      setLines([]);
      return;
    }

    const token = localStorage.getItem('access_token') ?? '';
    const wsUrl =
      `${import.meta.env.VITE_WS_URL}/ws/servers/${serverId}/containers/${containerId}/logs` +
      `?token=${token}&tail=${tail}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => { setConnected(false); wsRef.current = null; };
    ws.onerror = () => { setConnected(false); wsRef.current = null; };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as { type: string; data: string };
        if (msg.type === 'log') {
          setLines((prev) => {
            const next = [...prev, msg.data];
            return next.length > 2000 ? next.slice(-2000) : next;
          });
        }
      } catch {
        // ignore malformed frame
      }
    };

    return () => { ws.close(); };
  }, [enabled, serverId, containerId, tail]);

  return { lines, connected };
}
