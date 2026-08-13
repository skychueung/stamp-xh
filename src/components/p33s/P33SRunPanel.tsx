import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Ban,
  FileJson,
  FlaskConical,
  Gauge,
  Loader2,
  Lock,
  Play,
  RefreshCw,
  ShieldAlert,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  fetchScorerAvailability,
  p33sProbe,
  p33sDryRun,
  p33sRealRun,
  p33sJobStatus,
  p33sCancel,
  p33sManifest,
  type P33SScorerAvailability,
  type P33SPipelineSummary,
} from "@/lib/api/p33s";
import { D29SmokeCandidateSection } from "./D29SmokeCandidateSection";

const MODEL_LABELS: Record<string, string> = {
  pepmlm: "PepMLM",
  evobind2: "EvoBind2",
  diffpepbuilder: "DiffPepBuilder",
  pepflow: "PepFlow",
  pephar: "PepHAR",
  ppflow: "PPFlow",
};

const MODEL_ORDER = [
  "pepmlm",
  "evobind2",
  "diffpepbuilder",
  "pepflow",
  "pephar",
  "ppflow",
];

const STATUS_TONE: Record<string, string> = {
  ok: "bg-emerald-100 text-emerald-700",
  unavailable_with_reason: "bg-rose-100 text-rose-700",
  failed_with_evidence: "bg-amber-100 text-amber-700",
  not_applicable: "bg-slate-100 text-slate-600",
  BLOCKED: "bg-purple-100 text-purple-700",
};

function Banner() {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
      <ShieldAlert className="h-4 w-4" />
      COMPUTATIONAL PREDICTION ONLY / NOT EXPERIMENTALLY VALIDATED
    </div>
  );
}

export function P33SRunPanel() {
  const [avail, setAvail] = useState<P33SScorerAvailability | null>(null);
  const [modelId, setModelId] = useState<string>("pepmlm");
  const [targetSeq, setTargetSeq] = useState<string>("ACDEFGHIKLMNPQRSTVWY");
  const [pepLen, setPepLen] = useState<number>(10);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<P33SPipelineSummary | null>(null);
  const [jobId, setJobId] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);

  const loadAvail = async () => {
    try {
      setAvail(await fetchScorerAvailability());
      setError("");
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    loadAvail();
  }, []);

  const req = (): Parameters<typeof p33sDryRun>[1] => ({
    target_sequence: targetSeq,
    peptide_length: pepLen,
    seed: 2024,
    gpu_device: null,
    max_wall_seconds: 1800,
    output_quota_bytes: 52428800,
  });

  const run = async (mode: "probe" | "dry" | "real") => {
    setBusy(true);
    setError("");
    setSummary(null);
    setManifest(null);
    try {
      let s: P33SPipelineSummary;
      if (mode === "probe") s = await p33sProbe(modelId);
      else if (mode === "dry") s = await p33sDryRun(modelId, req());
      else s = await p33sRealRun(modelId, req());
      setSummary(s);
      if (s.job_id) setJobId(s.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const refreshStatus = async () => {
    if (!jobId) return;
    try {
      setSummary(await p33sJobStatus(modelId, jobId));
    } catch (e) {
      setError(String(e));
    }
  };

  const cancel = async () => {
    if (!jobId) return;
    setBusy(true);
    try {
      await p33sCancel(modelId, jobId);
      await refreshStatus();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const loadManifest = async () => {
    if (!jobId) return;
    try {
      setManifest(await p33sManifest(modelId, jobId));
    } catch (e) {
      setError(String(e));
    }
  };

  const modelUnavailable = avail?.models?.[modelId]?.unavailable;
  // Real-run is allowed only when model is available AND all three registry flags pass.
  // The backend enforces this (returns 403/BLOCKED otherwise); the button is a UX guard.
  const realRunDisabled = !avail || !!modelUnavailable;

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <FlaskConical className="h-4 w-4" /> P33S Real-Model GPU + Scientific Scoring
        </CardTitle>
        <Button variant="outline" size="sm" onClick={loadAvail} disabled={busy}>
          <RefreshCw className="mr-1 h-3 w-3" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <Banner />

        {/* Scorer availability — real-state driven, never hardcoded */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <Gauge className="h-4 w-4" /> Scientific Scorer Availability
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {avail?.scorers
              ? Object.entries(avail.scorers).map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold uppercase">{k}</span>
                      <Badge className={STATUS_TONE[v.status] ?? "bg-slate-100"}>
                        {v.status}
                      </Badge>
                    </div>
                    <div className="mt-1 text-slate-500">{v.backend}</div>
                    {v.label ? (
                      <div className="text-slate-600">label: {v.label}</div>
                    ) : null}
                    {v.reason ? (
                      <div className="text-rose-600">{v.reason}</div>
                    ) : null}
                    {v.real_cpu_test ? (
                      <div className="text-emerald-700">{v.real_cpu_test}</div>
                    ) : null}
                  </div>
                ))
              : null}
          </div>
        </div>

        {/* Model selector */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="text-xs font-medium text-slate-600">Model</label>
            <select
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              {MODEL_ORDER.map((m) => {
                const u = avail?.models?.[m]?.unavailable;
                return (
                  <option key={m} value={m}>
                    {MODEL_LABELS[m]} {u ? "(unavailable)" : ""}
                  </option>
                );
              })}
            </select>
            {modelUnavailable ? (
              <div className="mt-1 text-xs text-rose-600">
                {avail?.models?.[modelId]?.unavailable_reason}
              </div>
            ) : null}
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">
              Target sequence
            </label>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 font-mono text-sm"
              value={targetSeq}
              onChange={(e) => setTargetSeq(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">
              Peptide length
            </label>
            <input
              type="number"
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={pepLen}
              onChange={(e) => setPepLen(Number(e.target.value))}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => run("probe")} disabled={busy}>
            <Terminal className="mr-1 h-3 w-3" /> Probe
          </Button>
          <Button size="sm" variant="outline" onClick={() => run("dry")} disabled={busy}>
            <FileJson className="mr-1 h-3 w-3" /> Dry-Run
          </Button>
          <Button
            size="sm"
            onClick={() => run("real")}
            disabled={busy || realRunDisabled}
            title={realRunDisabled ? "Locked: model unavailable or real_run_enabled=false" : "Real run (gated)"}
          >
            {realRunDisabled ? <Lock className="mr-1 h-3 w-3" /> : <Play className="mr-1 h-3 w-3" />}
            Real Run
          </Button>
          {jobId ? (
            <>
              <Button size="sm" variant="outline" onClick={refreshStatus} disabled={busy}>
                <RefreshCw className="mr-1 h-3 w-3" /> Status
              </Button>
              <Button size="sm" variant="outline" onClick={loadManifest} disabled={busy}>
                <FileJson className="mr-1 h-3 w-3" /> Manifest
              </Button>
              <Button size="sm" variant="destructive" onClick={cancel} disabled={busy}>
                <Ban className="mr-1 h-3 w-3" /> Cancel
              </Button>
            </>
          ) : null}
        </div>

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            <AlertTriangle className="h-4 w-4" /> {error}
          </div>
        ) : null}

        {/* Result summary — metrics with predicted labels / version / confidence / unit */}
        {summary ? (
          <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="bg-slate-200 text-slate-700">{summary.mode}</Badge>
              {summary.job_id ? (
                <span className="text-xs text-slate-500">{summary.job_id}</span>
              ) : null}
              {summary.status ? (
                <Badge className={STATUS_TONE[summary.status] ?? "bg-slate-100"}>
                  {summary.status}
                </Badge>
              ) : null}
              <span className="text-xs text-slate-500">
                {summary.validation_status}
              </span>
            </div>
            {summary.reason ? (
              <div className="text-xs text-rose-700">{summary.reason}</div>
            ) : null}
            {summary.stages?.map((st) => (
              <div
                key={st.stage}
                className="rounded-md border border-slate-200 bg-white p-2 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold uppercase">{st.stage}</span>
                  <Badge className={STATUS_TONE[st.status] ?? "bg-slate-100"}>
                    {st.status}
                  </Badge>
                </div>
                {st.detail && typeof st.detail === "object" ? (
                  <div className="mt-1 grid gap-0.5 text-slate-600">
                    {"value" in st.detail && st.detail.value != null ? (
                      <div>
                        value: {String(st.detail.value)} {String(st.detail.unit ?? "")}
                      </div>
                    ) : null}
                    {"model_or_algorithm" in st.detail ? (
                      <div>algorithm: {String(st.detail.model_or_algorithm)}</div>
                    ) : null}
                    {"model_version" in st.detail ? (
                      <div>version: {String(st.detail.model_version)}</div>
                    ) : null}
                    {"confidence" in st.detail ? (
                      <div>confidence: {String(st.detail.confidence)}</div>
                    ) : null}
                    {"label" in st.detail ? (
                      <div>label: {String(st.detail.label)}</div>
                    ) : null}
                    {"reason" in st.detail ? (
                      <div className="text-rose-600">
                        reason: {String(st.detail.reason)}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {/* Manifest viewer */}
        {manifest ? (
          <details className="rounded-md border border-slate-200 bg-white p-2 text-xs">
            <summary className="cursor-pointer font-medium">
              Provenance manifest (JSON)
            </summary>
            <pre className="mt-2 max-h-80 overflow-auto text-[10px]">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          </details>
        ) : null}

        {busy ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="h-3 w-3 animate-spin" /> working…
          </div>
        ) : null}

        {/* D29: D28 EvoBind2 smoke candidate section */}
        <D29SmokeCandidateSection />
      </CardContent>
    </Card>
  );
}
