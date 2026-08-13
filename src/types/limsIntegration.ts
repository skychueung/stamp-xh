/**
 * STAMP v1.2 — LIMS/ELN Integration Types
 * Mirrors backend/app/routers/lims_integration.py schemas
 */

export type IntegrationType = "LIMS" | "ELN";

export type AuthMode = "token" | "oauth2" | "basic";

export type IntegrationStatus =
  | "CONFIG_REQUIRED"
  | "REAL_API_READY"
  | "TEST_FAILED"
  | "SYNC_SUCCEEDED"
  | "SYNC_FAILED";

export interface IntegrationConfig {
  id: string;
  integration_type: IntegrationType;
  name: string;
  base_url: string | null;
  auth_mode: AuthMode;
  token_secret_ref: string | null;
  field_mapping_json: Record<string, unknown>;
  status: IntegrationStatus;
  last_sync_at: string | null;
  last_error: string | null;
  enabled: boolean;
  test_mode: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntegrationConfigCreatePayload {
  integration_type: IntegrationType;
  name: string;
  base_url?: string | null;
  auth_mode?: AuthMode;
  token_secret_ref?: string | null;
  field_mapping_json?: Record<string, unknown>;
  enabled?: boolean;
  test_mode?: boolean;
}

export interface IntegrationConfigUpdatePayload {
  name?: string;
  base_url?: string | null;
  auth_mode?: AuthMode;
  token_secret_ref?: string | null;
  field_mapping_json?: Record<string, unknown>;
  enabled?: boolean;
  test_mode?: boolean;
}

export interface IntegrationConfigListResponse {
  items: IntegrationConfig[];
  total: number;
  limit: number;
  offset: number;
}
