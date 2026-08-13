import { useEffect, useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { auditLogsApi } from '@/lib/api/auditLogs';
import { useAuth } from '@/contexts/AuthContext';
import type { AuditLogEntry } from '@/types/auditLog';
import {
  ClipboardList,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Search,
  ShieldAlert,
} from 'lucide-react';

export default function AuditLogsPage() {
  const { isAdmin } = useAuth();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filters, setFilters] = useState({
    entity_type: '',
    entity_id: '',
    user_id: '',
    limit: 50,
  });

  const load = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await auditLogsApi.list({
        entity_type: filters.entity_type || undefined,
        entity_id: filters.entity_id || undefined,
        user_id: filters.user_id || undefined,
        limit: filters.limit,
      });
      setEntries(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load audit logs');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      load();
    }
  }, [isAdmin]);

  if (!isAdmin) {
    return (
      <PlatformLayout>
        <div className="max-w-5xl mx-auto px-6 py-8">
          <div className="p-6 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-sm font-semibold text-amber-800">Access Restricted</h2>
              <p className="text-xs text-amber-700 mt-1">
                Audit logs are only accessible to admin users.
              </p>
            </div>
          </div>
        </div>
      </PlatformLayout>
    );
  }

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <ClipboardList className="w-6 h-6 text-xh-primary" />
            Audit Logs
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Append-only audit trail of system actions. Filter by entity or user.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-40">
              <label className="block text-xs font-medium text-slate-700 mb-1">Entity Type</label>
              <input
                type="text"
                value={filters.entity_type}
                onChange={(e) => setFilters({ ...filters, entity_type: e.target.value })}
                placeholder="e.g., job"
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              />
            </div>
            <div className="w-40">
              <label className="block text-xs font-medium text-slate-700 mb-1">Entity ID</label>
              <input
                type="text"
                value={filters.entity_id}
                onChange={(e) => setFilters({ ...filters, entity_id: e.target.value })}
                placeholder="e.g., job-id"
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              />
            </div>
            <div className="w-40">
              <label className="block text-xs font-medium text-slate-700 mb-1">User ID</label>
              <input
                type="text"
                value={filters.user_id}
                onChange={(e) => setFilters({ ...filters, user_id: e.target.value })}
                placeholder="e.g., user-001"
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              />
            </div>
            <div className="w-28">
              <label className="block text-xs font-medium text-slate-700 mb-1">Limit</label>
              <select
                value={filters.limit}
                onChange={(e) => setFilters({ ...filters, limit: Number(e.target.value) })}
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
            <button
              onClick={load}
              disabled={isLoading}
              className="flex items-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Search
            </button>
            <button
              onClick={load}
              disabled={isLoading}
              className="flex items-center gap-1 text-xs text-xh-primary hover:underline disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Time</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Action</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Entity</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">User</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-400">
                    No audit log entries found.
                  </td>
                </tr>
              ) : (
                entries.map((e) => (
                  <tr key={e.event_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-2 text-slate-500 whitespace-nowrap">
                      {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-2">
                      <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                        {e.action}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-slate-700">
                      {e.entity_type} / {e.entity_id}
                    </td>
                    <td className="px-4 py-2 text-slate-500">
                      {e.user_id || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </PlatformLayout>
  );
}
