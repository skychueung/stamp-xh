import { fetchClient } from './client';

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface DbHealth {
  status: string;
  database: string;
  reachable: boolean;
  error?: string;
}

export interface StorageCheck {
  exists: boolean;
  writable: boolean;
}

export interface StorageHealth {
  status: string;
  checks: Record<string, StorageCheck>;
}

export interface QueueHealth {
  status: string;
  total_jobs: number;
  breakdown: {
    pending: number;
    running: number;
    succeeded: number;
    failed: number;
    blocked: number;
  };
  error?: string;
}

export interface GpuInfo {
  index: number;
  name: string;
  memory_used_mb: number;
  memory_total_mb: number;
  memory_free_mb: number;
  utilization_percent: number;
}

export interface CpuInfo {
  cores: number | null;
  load_1min: number | null;
  utilization_percent: number | null;
}

export interface RamInfo {
  total_mb: number | null;
  used_mb: number | null;
  free_mb: number | null;
  utilization_percent: number | null;
}

export interface DiskInfo {
  total_gb: number | null;
  used_gb: number | null;
  free_gb: number | null;
  utilization_percent: number | null;
}

export interface GpuLockInfo {
  locked: boolean;
  holder: string | null;
  held_since_seconds: number | null;
}

export interface ResourceHealth {
  status: string;
  gpus: GpuInfo[];
  cpu: CpuInfo;
  ram: RamInfo;
  disk: DiskInfo;
  gpu_lock: GpuLockInfo;
  blocked_reasons: string[] | null;
}

export const healthApi = {
  health: () => fetchClient<HealthStatus>('/health'),
  db: () => fetchClient<DbHealth>('/health/db'),
  storage: () => fetchClient<StorageHealth>('/health/storage'),
  queue: () => fetchClient<QueueHealth>('/health/queue'),
  resources: () => fetchClient<ResourceHealth>('/health/resources'),
};
