import { useState } from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Download,
  FileJson,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  Timer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useP33L } from "@/hooks/useP33L";
import type { P33LJobResponse } from "@/lib/api/p33l";

const MODEL_LABELS: Record<string, string> = {
  pepmlm: "PepMLM",
  evobind2: "EvoBind2",
  diffpepbuilder: "DiffPepBuilder",
  pepflow: "PepFlow",
  pephar: "PepHAR",
  ppflow: "PPFlow",
};

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-blue-100 text-blue-700",
  succeeded: "bg-emerald-100 text-emerald-700",
  failed: "bg-rose-100 text-rose-700",
  timeout: "bg-amber-100 text-amber-700",
  cancelled: "bg-gray-100 text-gray-700",
  blocked: "bg-purple-100 text-purple-700",
};

function formatDuration(startedAt: string | null, finishedAt: string | null): string {
  if (!startedAt) return "—";
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - new Date(startedAt).getTime()) / 1000));
  return `${seconds}s`;
}

function JobResult({ job, downloadUrl }: { job: P33LJobResponse; downloadUrl: (path: string) => string }) {
  const result = job.result as Record<string, unknown> | undefined;
  const quotaError = result?.quota_error as string | undefined;
  const command = Array.isArray(result?.command) ? (result.command as string[]) : [];

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={STATUS_COLORS[job.status] ?? "bg-slate-100 text-slate-700"}>
          {job.status}
        </Badge>
        <span className="text-xs text-slate-500">{job.job_id}</span>
        {job.pid ? <span className="text-xs text-slate-500">PID {job.pid}</span> : null}
      </div>

      <div className="grid gap-2 text-sm sm:grid-cols-3">
        <div>
          <span className="text-slate-500">Started:</span>{" "}
          {job.started_at ? new Date(job.started_at).toLocaleTimeString() : "—"}
        </div>
        <div>
          <span className="text-slate-500">Finished:</span>{" "}
          {job.finished_at ? new Date(job.finished_at).toLocaleTimeString() : "—"}
        </div>
        <div>
          <span className="text-slate-500">Duration:</span>{" "}
          {formatDuration(job.started_at, job.finished_at)}
        </div>
      </div>

      {typeof result?.exit_code === "number" && (
        <div className="text-sm">
          <span className="text-slate-500">Exit code:</span> {result.exit_code}
        </div>
      )}

      {quotaError && (
        <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
          <Ban className="mb-1 h-4 w-4" />
          Quota violation: {quotaError}
        </div>
      )}

      {Boolean(result?.error) && (
        <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
          {String(result?.error)}
        </div>
      )}

      {command.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-600">Command</summary>
          <code className="mt-2 block max-h-32 overflow-auto whitespace-pre-wrap rounded bg-white p-2 text-xs text-slate-700">
            {command.join(" ")}
          </code>
        </details>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        <a
          href={downloadUrl("logs/run_stdout_stderr.log")}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <Download className="h-3.5 w-3.5" />
          Log
        </a>
        <a
          href={downloadUrl("manifest/run_manifest.json")}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <FileJson className="h-3.5 w-3.5" />
          Manifest
        </a>
        <a
          href={downloadUrl("manifest/sha256_manifest.txt")}
          download
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          <ShieldAlert className="h-3.5 w-3.5" />
          SHA256 manifest
        </a>
      </div>
    </div>
  );
}

export function P33LRunPanel() {
  const {
    authorized,
    manifestSha,
    status,
    currentJob,
    loading,
    running,
    error,
    nextModelId,
    runNextModel,
    cancelCurrent,
    refreshStatus,
    downloadUrl,
  } = useP33L();

  const [modelVariant, setModelVariant] = useState<string>("prediction");

  const completedCount = status?.completed_models.length ?? 0;
  const totalCount = 6;

  const handleRun = async () => {
    const input: Record<string, unknown> = {};
    if (nextModelId === "pephar") {
      input.model_variant = modelVariant;
    }
    await runNextModel(nextModelId, input);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking P33L authorization...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!authorized || !manifestSha) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-5 w-5 text-slate-400" />
            P33L Six-Model Real Run
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-slate-500">
          P33L real runs are not authorized on this backend. The dev backend must be started with
          <code className="mx-1 rounded bg-slate-100 px-1">P33L_AUTHORIZED_MANIFEST_SHA</code> set.
        </CardContent>
      </Card>
    );
  }

  const canRun = !running && !!nextModelId && !status?.failed_model;

  return (
    <Card className="border-amber-200 bg-amber-50/40">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Play className="h-5 w-5 text-amber-600" />
            P33L Six-Model Real Run & Deliver
          </CardTitle>
          <Badge variant="outline" className="shrink-0 text-xs">
            NOT_EXPERIMENTALLY_VALIDATED
          </Badge>
        </div>
        <p className="text-xs text-slate-500">
          Fixed order, one attempt per model, fail-stop. Authorized manifest SHA is set on the
          backend.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Scientific disclaimer</p>
              <p>
                All outputs from this run are computational predictions only and are explicitly
                marked NOT_EXPERIMENTALLY_VALIDATED. They must not be used as experimental evidence.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-sm">
          <span className="text-slate-500">Progress:</span>
          <div className="flex-1">
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-amber-500 transition-all"
                style={{ width: `${(completedCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
          <span className="text-xs font-medium text-slate-600">
            {completedCount}/{totalCount}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-sm">
          {["pepmlm", "evobind2", "diffpepbuilder", "pepflow", "pephar", "ppflow"].map((m) => {
            const done = status?.completed_models.includes(m);
            const failed = status?.failed_model === m;
            const next = nextModelId === m && !done && !failed;
            return (
              <Badge
                key={m}
                variant={next ? "default" : "outline"}
                className={
                  done
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : failed
                      ? "border-rose-200 bg-rose-50 text-rose-700"
                      : next
                        ? "bg-amber-600 text-white"
                        : "text-slate-500"
                }
              >
                {done && <CheckCircle2 className="mr-1 h-3 w-3" />}
                {failed && <Ban className="mr-1 h-3 w-3" />}
                {MODEL_LABELS[m]}
              </Badge>
            );
          })}
        </div>

        {nextModelId === "pephar" && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">PepHAR variant:</span>
            <select
              value={modelVariant}
              onChange={(e) => setModelVariant(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              disabled={running}
            >
              <option value="prediction">prediction</option>
              <option value="density">density</option>
            </select>
          </div>
        )}

        {status?.failed_model && (
          <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
            <Ban className="mb-1 h-4 w-4" />
            P33L stopped because <strong>{MODEL_LABELS[status.failed_model]}</strong> failed. No
            further models will run.
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleRun}
            disabled={!canRun}
            className="bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {running ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {running
              ? `Running ${MODEL_LABELS[nextModelId] ?? nextModelId}...`
              : nextModelId
                ? `Run ${MODEL_LABELS[nextModelId]}`
                : "All models completed"}
          </Button>

          {running && currentJob && (
            <Button variant="outline" onClick={cancelCurrent} className="border-rose-300 text-rose-700 hover:bg-rose-50">
              <Timer className="mr-2 h-4 w-4" />
              Cancel
            </Button>
          )}

          <Button variant="outline" onClick={refreshStatus} disabled={running}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>

        {currentJob && (
          <JobResult job={currentJob} downloadUrl={downloadUrl} />
        )}
      </CardContent>
    </Card>
  );
}
