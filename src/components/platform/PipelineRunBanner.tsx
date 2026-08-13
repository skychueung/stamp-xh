import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { pipelineRunsApi, type PipelineStatus } from '@/lib/api/pipelineRuns';
import { GitBranch, ArrowLeft, AlertTriangle } from 'lucide-react';

export default function PipelineRunBanner() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const runId = searchParams.get('pipeline_run_id');
  const [run, setRun] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    pipelineRunsApi.get(runId)
      .then(setRun)
      .catch(() => setRun(null))
      .finally(() => setLoading(false));
  }, [runId]);

  if (!runId) return null;

  return (
    <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-start justify-between gap-3">
      <div className="flex items-start gap-2 min-w-0">
        <GitBranch className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-blue-900 truncate">
            {loading ? '加载 Pipeline Run...' : run ? `Pipeline Run: ${run.target_name}` : 'Pipeline Run'}
          </p>
          <p className="text-xs text-blue-700 mt-0.5">
            ID: {runId.slice(0, 16)}... · 状态: {run?.status || 'unknown'}
          </p>
          <p className="text-xs text-blue-600 mt-1 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            Sequence-level computational prioritization; not experimentally validated.
          </p>
        </div>
      </div>
      <button
        onClick={() => navigate('/filter')}
        className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-md bg-white border border-blue-200 text-xs font-medium text-blue-700 hover:bg-blue-50 transition-colors"
      >
        <ArrowLeft className="w-3 h-3" />
        返回 Pipeline
      </button>
    </div>
  );
}
