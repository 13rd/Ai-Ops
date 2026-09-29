export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface APIResponse<T = null> {
  success: boolean;
  data: T;
  message: string;
  error: ErrorDetail | null;
}

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface PaginatedData<T> {
  items: T[];
  pagination: PaginationMeta;
}

export class ApiError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
}

export function unwrap<T>(response: { data: APIResponse<T> }): T {
  const body = response.data;
  if (!body.success) {
    const err = body.error;
    throw new ApiError(err?.code ?? 'unknown_error', err?.message ?? body.message, err?.details);
  }
  return body.data;
}
