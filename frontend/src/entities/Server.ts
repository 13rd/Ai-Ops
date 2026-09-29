export type ServerStatus = 'online' | 'offline' | 'degraded';

export interface Server {
  id: number;
  name: string;
  host: string;
  port: number;
  connection_type: string;
  environment: string | null;
  tags: string[];
  status: ServerStatus;
  last_seen: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServerFilters {
  skip?: number;
  limit?: number;
  environment?: string;
  status?: string;
  tags?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ServerCreatePayload {
  name: string;
  host: string;
  port: number;
  connection_type: string;
  environment?: string;
  tags: string[];
  ssh_username?: string;
  ssh_password?: string;
  ssh_private_key?: string;
}

export interface ServerUpdatePayload extends Partial<ServerCreatePayload> {}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  error_code: string | null;
}

export interface MyServerAccess {
  server: Server;
  permission: 'read' | 'write';
}

export interface ServerPermissionResult {
  permission: 'read' | 'write' | null;
}
