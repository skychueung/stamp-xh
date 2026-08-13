import { fetchClient } from './client';
import type { AuditLogEntry } from '@/types/auditLog';

export const auditLogsApi = {
  list: (params?: {
    entity_type?: string;
    entity_id?: string;
    user_id?: string;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.entity_type) search.append('entity_type', params.entity_type);
    if (params?.entity_id) search.append('entity_id', params.entity_id);
    if (params?.user_id) search.append('user_id', params.user_id);
    if (params?.limit !== undefined) search.append('limit', String(params.limit));
    if (params?.offset !== undefined) search.append('offset', String(params.offset));
    const query = search.toString();
    return fetchClient<AuditLogEntry[]>(`/audit-log${query ? `?${query}` : ''}`);
  },
};
