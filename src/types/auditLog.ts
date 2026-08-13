/**
 * STAMP v1.2 — Audit Log Types
 * Mirrors backend/app/routers/audit_logs.py schemas
 */

export interface AuditLogEntry {
  event_id: string;
  timestamp: string | null;
  user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  session_id: string | null;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
}
