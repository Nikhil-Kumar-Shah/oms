/**
 * API Standard Request & Response Types
 * Aligned with FastAPI server-authoritative response contracts.
 */

export interface ApiError {
  code: string;
  message: string;
  details?: {
    field?: string;
    validation_errors?: Array<{ field: string; message: string }>;
    [key: string]: unknown;
  };
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: ApiError;
  [key: string]: unknown;
}

export interface ResourceGroup {
  group: string;
  prefix: string;
  description: string;
}

export interface ApiDiscoveryResponse {
  name: string;
  version: string;
  status: string;
  authenticated_as?: string;
  documentation: {
    swagger_ui: string;
    redoc: string;
    openapi_spec: string;
  };
  resource_groups: ResourceGroup[];
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
}
