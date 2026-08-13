import { useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { fileAssetsApi } from '@/lib/api/fileAssets';
import { useAuth } from '@/contexts/AuthContext';
import type { FileAsset } from '@/types/fileAsset';
import {
  FolderOpen,
  Loader2,
  AlertTriangle,
  Search,
  FileText,
  Package,
} from 'lucide-react';

export default function FileManagerPage() {
  useAuth();
  const [jobId, setJobId] = useState('');
  const [batchId, setBatchId] = useState('');
  const [assets, setAssets] = useState<FileAsset[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!jobId.trim() && !batchId.trim()) {
      setError('Please enter a Job ID or Batch ID');
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      let data: FileAsset[];
      if (batchId.trim()) {
        data = await fileAssetsApi.listByBatch(batchId);
      } else {
        data = await fileAssetsApi.listByJob(jobId);
      }
      setAssets(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load assets');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadBundle = async () => {
    if (!batchId.trim()) {
      setError('Enter a Batch ID to download bundle');
      return;
    }
    try {
      setError(null);
      const blob = await fileAssetsApi.downloadBundle(batchId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_${batchId}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Download failed');
    }
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <FolderOpen className="w-6 h-6 text-xh-primary" />
            File Manager
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Browse file assets by job or batch. Download bundles as tar.gz archives.
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
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-slate-700 mb-1">Job ID</label>
              <input
                type="text"
                value={jobId}
                onChange={(e) => { setJobId(e.target.value); setBatchId(''); }}
                placeholder="e.g., job-001"
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-slate-700 mb-1">Batch ID</label>
              <input
                type="text"
                value={batchId}
                onChange={(e) => { setBatchId(e.target.value); setJobId(''); }}
                placeholder="e.g., batch-001"
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={isLoading}
              className="flex items-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Search
            </button>
            <button
              onClick={handleDownloadBundle}
              disabled={!batchId.trim()}
              className="flex items-center gap-2 bg-slate-800 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-slate-700 disabled:opacity-50 transition-colors"
            >
              <Package className="w-4 h-4" />
              Download Bundle
            </button>
          </div>
        </div>

        {assets.length === 0 && !isLoading && (
          <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
            <FolderOpen className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Enter a Job ID or Batch ID to search assets.</p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {assets.map((asset) => (
            <div
              key={asset.asset_id}
              className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm transition-shadow flex items-start gap-3"
            >
              <FileText className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{asset.original_filename}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                    {asset.file_type}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {(asset.size_bytes / 1024).toFixed(1)} KB
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 font-mono mt-1 truncate">
                  {asset.sha256 || 'No checksum'}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </PlatformLayout>
  );
}
