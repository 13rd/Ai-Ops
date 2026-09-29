export type UserRole = 'admin' | 'operator';
export type ServerPermission = 'read' | 'write';

export interface AppUser {
  id: number;
  email: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ServerAccess {
  server_id: number;
  permission: ServerPermission;
  granted_at: string;
}

export interface UserCreatePayload {
  email: string;
  username: string;
  role: UserRole;
  password: string;
}

export interface UserUpdatePayload {
  email?: string;
  username?: string;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
}
