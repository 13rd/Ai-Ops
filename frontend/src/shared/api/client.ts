import axios, { type AxiosRequestConfig } from 'axios';
import { ApiError, type APIResponse } from './types';

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single-flight refresh promise
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  try {
    const res = await axios.post<APIResponse<{ access_token: string }>>(
      `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1'}/auth/refresh`,
      {},
      { withCredentials: true },
    );
    const body = res.data;
    if (!body.success || !body.data?.access_token) {
      throw new ApiError('refresh_failed', 'Token refresh failed');
    }
    return body.data.access_token;
  } finally {
    refreshPromise = null;
  }
}

// Convert backend envelope errors into ApiError so callers can check err.code
function toApiError(error: unknown): ApiError | null {
  if (!axios.isAxiosError(error)) return null;
  const body = error.response?.data as APIResponse<unknown> | undefined;
  if (!body || body.success !== false) return null;
  const err = body.error;
  if (!err) return new ApiError('server_error', body.message ?? 'Server error');
  return new ApiError(err.code, err.message, err.details);
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as AxiosRequestConfig & { _retry?: boolean };
    const isAuthEndpoint =
      config.url?.includes('/auth/login') || config.url?.includes('/auth/refresh');

    // Refresh on 401 for non-auth endpoints
    if (error.response?.status === 401 && !config._retry && !isAuthEndpoint) {
      config._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = doRefresh();
        }
        const newToken = await refreshPromise;
        setAccessToken(newToken);
        if (config.headers) {
          (config.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        }
        return apiClient(config);
      } catch {
        setAccessToken(null);
        window.dispatchEvent(new CustomEvent('auth:logout'));
        return Promise.reject(toApiError(error) ?? error);
      }
    }

    // Convert all backend envelope errors to ApiError
    const apiErr = toApiError(error);
    return Promise.reject(apiErr ?? error);
  },
);

export default apiClient;
