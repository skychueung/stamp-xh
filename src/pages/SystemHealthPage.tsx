import { useEffect, useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { healthApi } from '@/lib/api/health';
import type { HealthStatus, DbHealth, StorageHealth, QueueHealth, ResourceHealth } from '@/types/health';
import {
  HeartPulse,
  Loader2,
  Database,
  HardDrive,
  ListOrdered,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Cpu,
  MemoryStick,
  Monitor,
  Lock,
  Gpu,
} from 'lucide-react';

interface HealthCardProps {
  title: string;
  icon: React.ReactNode;
  loading: boolean;
  error: string | null;
  children: React.ReactNode;
  healthy?: boolean;
}

function HealthCard({ title, icon, loading, error, children, healthy }: HealthCardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        {loading && <Loader2 className="w-3 h-3 animate-spin text-slate-400 ml-auto" />}
        {!loading && healthy === true && <CheckCircle2 className="w-4 h-4 text-emerald-500 ml-auto" />}
        {!loading && healthy === false && <XCircle className="w-4 h-4 text-red-500 ml-auto" />}
      </div>
      {error ? (
        <p className="text-xs text-red-600">{error}</p>
      ) : (
        children
      )}
    </div>
  );
}

export default function SystemHealthPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [db, setDb] = useState<DbHealth | null>(null);
  const [storage, setStorage] = useState<StorageHealth | null>(null);
  const [queue, setQueue] = useState<QueueHealth | null>(null);
  const [resources, setResources] = useState<ResourceHealth | null>(null);
  const [loading, setLoading] = useState<Record<string, boolean>>({
    health: false,
    db: false,
    storage: false,
    queue: false,
    resources: false,
  });
  const [errors, setErrors] = useState<Record<string, string | null>>({
    health: null,
    db: null,
    storage: null,
    queue: null,
    resources: null,
  });

  const loadAll = async () => {
    const checks = [
      { key: 'health', fn: healthApi.health },
      { key: 'db', fn: healthApi.db },
      { key: 'storage', fn: healthApi.storage },
      { key: 'queue', fn: healthApi.queue },
      { key: 'resources', fn: healthApi.resources },
    ] as const;

    setLoading((prev) => ({
      ...prev,
      health: true,
      db: true,
      storage: true,
      queue: true,
      resources: true,
    }));
    setErrors({ health: null, db: null, storage: null, queue: null, resources: null });

    await Promise.all(
      checks.map(async ({ key, fn }) => {
        try {
          const data = await fn();
          if (key === 'health') setHealth(data as HealthStatus);
          if (key === 'db') setDb(data as DbHealth);
          if (key === 'storage') setStorage(data as StorageHealth);
          if (key === 'queue') setQueue(data as QueueHealth);
          if (key === 'resources') setResources(data as ResourceHealth);
        } catch (err: any) {
          setErrors((prev) => ({ ...prev, [key]: err?.message || 'Check failed' }));
        } finally {
          setLoading((prev) => ({ ...prev, [key]: false }));
        }
      })
    );
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <HeartPulse className="w-6 h-6 text-xh-primary" />
              System Health
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Real-time backend health checks. Auto-refreshes every 30 seconds.
            </p>
          </div>
          <button
            onClick={loadAll}
            className="text-xs flex items-center gap-1 px-3 py-2 rounded border border-slate-200 hover:bg-slate-50"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh Now
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <HealthCard
            title="Backend Liveness"
            icon={<HeartPulse className="w-4 h-4 text-xh-primary" />}
            loading={loading.health}
            error={errors.health}
            healthy={health?.status === 'healthy'}
          >
            {health && (
              <div className="space-y-1">
                <p className="text-xs text-slate-700"><span className="font-medium">Service:</span> {health.service}</p>
                <p className="text-xs text-slate-700"><span className="font-medium">Version:</span> {health.version}</p>
                <p className="text-xs text-slate-500">{health.timestamp}</p>
              </div>
            )}
          </HealthCard>

          <HealthCard
            title="Database"
            icon={<Database className="w-4 h-4 text-xh-primary" />}
            loading={loading.db}
            error={errors.db}
            healthy={db?.reachable === true}
          >
            {db && (
              <div className="space-y-1">
                <p className="text-xs text-slate-700"><span className="font-medium">Engine:</span> {db.database}</p>
                <p className="text-xs text-slate-700"><span className="font-medium">Reachable:</span> {db.reachable ? 'Yes' : 'No'}</p>
                {db.error && <p className="text-xs text-red-600">{db.error}</p>}
              </div>
            )}
          </HealthCard>

          <HealthCard
            title="Storage"
            icon={<HardDrive className="w-4 h-4 text-xh-primary" />}
            loading={loading.storage}
            error={errors.storage}
            healthy={storage?.status === 'healthy'}
          >
            {storage && (
              <div className="space-y-1">
                <p className="text-xs text-slate-700"><span className="font-medium">Overall:</span> {storage.status}</p>
                {Object.entries(storage.checks).map(([path, check]) => (
                  <div key={path} className="flex items-center gap-2 text-[10px]">
                    <span className="text-slate-500">{path}</span>
                    {check.exists ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <XCircle className="w-3 h-3 text-red-500" />
                    )}
                    <span className={check.writable ? 'text-emerald-600' : 'text-red-600'}>
                      {check.writable ? 'writable' : 'read-only'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </HealthCard>

          <HealthCard
            title="Job Queue"
            icon={<ListOrdered className="w-4 h-4 text-xh-primary" />}
            loading={loading.queue}
            error={errors.queue}
            healthy={queue?.status === 'healthy'}
          >
            {queue && (
              <div className="space-y-1">
                <p className="text-xs text-slate-700"><span className="font-medium">Total:</span> {queue.total_jobs}</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {Object.entries(queue.breakdown).map(([key, count]) => (
                    <span key={key} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                      {key}: {count}
                    </span>
                  ))}
                </div>
                {queue.error && <p className="text-xs text-red-600">{queue.error}</p>}
              </div>
            )}
          </HealthCard>

          <HealthCard
            title="Resources"
            icon={<Monitor className="w-4 h-4 text-xh-primary" />}
            loading={loading.resources}
            error={errors.resources}
            healthy={resources?.status === 'healthy'}
          >
            {resources && (
              <div className="space-y-2">
                {resources.blocked_reasons && (
                  <div className="rounded bg-red-50 border border-red-100 p-2">
                    <p className="text-[10px] font-semibold text-red-700 mb-0.5">BLOCKED</p>
                    {resources.blocked_reasons.map((r) => (
                      <p key={r} className="text-[10px] text-red-600">• {r}</p>
                    ))}
                  </div>
                )}

                {/* GPUs */}
                <div>
                  <p className="text-[10px] font-medium text-slate-500 mb-1 flex items-center gap-1">
                    <Gpu className="w-3 h-3" /> GPU
                  </p>
                  {resources.gpus.length === 0 ? (
                    <p className="text-[10px] text-slate-400">No GPUs detected</p>
                  ) : (
                    <div className="space-y-1">
                      {resources.gpus.map((gpu) => (
                        <div key={gpu.index} className="text-[10px] space-y-0.5">
                          <p className="text-slate-700 font-medium">{gpu.name} <span className="text-slate-400">#{gpu.index}</span></p>
                          <div className="w-full bg-slate-100 rounded h-1.5 overflow-hidden">
                            <div
                              className="bg-xh-primary h-1.5 rounded"
                              style={{ width: `${Math.min(gpu.utilization_percent, 100)}%` }}
                            />
                          </div>
                          <div className="flex justify-between text-slate-500">
                            <span>Util: {gpu.utilization_percent}%</span>
                            <span>Mem: {gpu.memory_used_mb}/{gpu.memory_total_mb} MB</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* CPU */}
                <div>
                  <p className="text-[10px] font-medium text-slate-500 mb-1 flex items-center gap-1">
                    <Cpu className="w-3 h-3" /> CPU
                  </p>
                  {resources.cpu.utilization_percent !== null ? (
                    <div className="text-[10px] space-y-0.5">
                      <div className="w-full bg-slate-100 rounded h-1.5 overflow-hidden">
                        <div
                          className="bg-xh-primary h-1.5 rounded"
                          style={{ width: `${Math.min(resources.cpu.utilization_percent, 100)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-slate-500">
                        <span>Load: {resources.cpu.utilization_percent}%</span>
                        <span>Cores: {resources.cpu.cores ?? '-'}</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-400">CPU info unavailable</p>
                  )}
                </div>

                {/* RAM */}
                <div>
                  <p className="text-[10px] font-medium text-slate-500 mb-1 flex items-center gap-1">
                    <MemoryStick className="w-3 h-3" /> RAM
                  </p>
                  {resources.ram.utilization_percent !== null ? (
                    <div className="text-[10px] space-y-0.5">
                      <div className="w-full bg-slate-100 rounded h-1.5 overflow-hidden">
                        <div
                          className="bg-xh-primary h-1.5 rounded"
                          style={{ width: `${Math.min(resources.ram.utilization_percent, 100)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-slate-500">
                        <span>Used: {resources.ram.utilization_percent}%</span>
                        <span>{resources.ram.used_mb} / {resources.ram.total_mb} MB</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-400">RAM info unavailable</p>
                  )}
                </div>

                {/* Disk */}
                <div>
                  <p className="text-[10px] font-medium text-slate-500 mb-1 flex items-center gap-1">
                    <HardDrive className="w-3 h-3" /> Disk
                  </p>
                  {resources.disk.utilization_percent !== null ? (
                    <div className="text-[10px] space-y-0.5">
                      <div className="w-full bg-slate-100 rounded h-1.5 overflow-hidden">
                        <div
                          className="bg-xh-primary h-1.5 rounded"
                          style={{ width: `${Math.min(resources.disk.utilization_percent, 100)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-slate-500">
                        <span>Used: {resources.disk.utilization_percent}%</span>
                        <span>{resources.disk.used_gb} / {resources.disk.total_gb} GB</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-400">Disk info unavailable</p>
                  )}
                </div>

                {/* GPU Lock */}
                <div className="flex items-center gap-2 text-[10px]">
                  <Lock className="w-3 h-3 text-slate-400" />
                  <span className="text-slate-500">GPU Lock:</span>
                  {resources.gpu_lock.locked ? (
                    <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-100">
                      Locked by {resources.gpu_lock.holder}
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-100">
                      Free
                    </span>
                  )}
                </div>
              </div>
            )}
          </HealthCard>
        </div>
      </div>
    </PlatformLayout>
  );
}
