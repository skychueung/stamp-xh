import { useEffect, useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { limsIntegrationApi } from '@/lib/api/limsIntegration';
import { useAuth } from '@/contexts/AuthContext';
import type { IntegrationConfig, IntegrationConfigCreatePayload } from '@/types/limsIntegration';
import {
  Plug,
  Plus,
  RefreshCw,
  Loader2,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Settings,
  Activity,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  CONFIG_REQUIRED: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Settings className="w-3 h-3" /> },
  REAL_API_READY: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Activity className="w-3 h-3" /> },
  TEST_FAILED: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" /> },
  SYNC_SUCCEEDED: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" /> },
  SYNC_FAILED: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <AlertTriangle className="w-3 h-3" /> },
};

export default function LIMSIntegrationPage() {
  const { canSubmit, canManage } = useAuth();
  const [configs, setConfigs] = useState<IntegrationConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<IntegrationConfigCreatePayload>({
    integration_type: 'LIMS',
    name: '',
    base_url: '',
    auth_mode: 'token',
    token_secret_ref: '',
    enabled: false,
    test_mode: true,
  });

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const resp = await limsIntegrationApi.list();
      setConfigs(resp.items);
    } catch (err: any) {
      setError(err?.message || 'Failed to load integrations');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    try {
      setIsCreating(true);
      setError(null);
      await limsIntegrationApi.create(form);
      setForm({
        integration_type: 'LIMS',
        name: '',
        base_url: '',
        auth_mode: 'token',
        token_secret_ref: '',
        enabled: false,
        test_mode: true,
      });
      await loadConfigs();
    } catch (err: any) {
      setError(err?.message || 'Failed to create integration');
    } finally {
      setIsCreating(false);
    }
  };

  const handleTestSync = async (id: string) => {
    try {
      setTestingId(id);
      setError(null);
      await limsIntegrationApi.testSync(id);
      await loadConfigs();
    } catch (err: any) {
      setError(err?.message || 'Test sync failed');
    } finally {
      setTestingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this integration config?')) return;
    try {
      setError(null);
      await limsIntegrationApi.delete(id);
      await loadConfigs();
    } catch (err: any) {
      setError(err?.message || 'Failed to delete');
    }
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Plug className="w-6 h-6 text-xh-primary" />
            LIMS / ELN Integration
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Connect to external LIMS or ELN systems. Test connectivity before enabling sync.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Create form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <Plus className="w-4 h-4" /> New Integration
              </h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Type</label>
                  <select
                    value={form.integration_type}
                    onChange={(e) => setForm({ ...form, integration_type: e.target.value as any })}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  >
                    <option value="LIMS">LIMS</option>
                    <option value="ELN">ELN</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., LabWare LIMS"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Base URL</label>
                  <input
                    type="url"
                    value={form.base_url || ''}
                    onChange={(e) => setForm({ ...form, base_url: e.target.value || null })}
                    placeholder="https://lims.example.com/api/v1"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Auth Mode</label>
                  <select
                    value={form.auth_mode}
                    onChange={(e) => setForm({ ...form, auth_mode: e.target.value as any })}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  >
                    <option value="token">Token</option>
                    <option value="oauth2">OAuth2</option>
                    <option value="basic">Basic</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Token Secret Ref</label>
                  <input
                    type="text"
                    value={form.token_secret_ref || ''}
                    onChange={(e) => setForm({ ...form, token_secret_ref: e.target.value || null })}
                    placeholder="Env var or vault path"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.enabled}
                      onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                      className="rounded border-slate-300"
                    />
                    Enabled
                  </label>
                  <label className="flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={form.test_mode}
                      onChange={(e) => setForm({ ...form, test_mode: e.target.checked })}
                      className="rounded border-slate-300"
                    />
                    Test Mode
                  </label>
                </div>
                <button
                  type="submit"
                  disabled={isCreating || !form.name.trim() || !canSubmit}
                  className="w-full flex items-center justify-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  {canSubmit ? 'Create Integration' : 'View Only'}
                </button>
              </form>
            </div>
          </div>

          {/* List */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Plug className="w-4 h-4" /> Configured Integrations
              </h2>
              <button
                onClick={loadConfigs}
                disabled={isLoading}
                className="text-xs flex items-center gap-1 text-xh-primary hover:underline disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : configs.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
                <Plug className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No integrations configured. Create one to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {configs.map((cfg) => {
                  const style = STATUS_STYLES[cfg.status] || STATUS_STYLES.CONFIG_REQUIRED;
                  return (
                    <div
                      key={cfg.id}
                      className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900">{cfg.name}</h3>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              {cfg.integration_type}
                            </span>
                            {cfg.enabled ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-600">
                                Enabled
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500">
                                Disabled
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-1 truncate">{cfg.base_url || 'No base URL'}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                              {style.icon}
                              {cfg.status}
                            </span>
                            {cfg.last_error && (
                              <span className="text-[10px] text-red-600 truncate max-w-[300px]">{cfg.last_error}</span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 ml-3">
                          {canSubmit && (
                            <button
                              onClick={() => handleTestSync(cfg.id)}
                              disabled={testingId === cfg.id}
                              className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                              title="Test connection"
                            >
                              {testingId === cfg.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <RefreshCw className="w-3 h-3" />
                              )}
                              Test
                            </button>
                          )}
                          {canManage && (
                            <button
                              onClick={() => handleDelete(cfg.id)}
                              className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50"
                              title="Delete"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
