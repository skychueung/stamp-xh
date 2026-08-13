import { useEffect, useState } from "react";
import {
  AlertTriangle,
  FlaskConical,
  Loader2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface SmokeStructure {
  structure_id: string;
  structure_model: string;
  pdb_path: string;
  artifact_sha256: string;
}

interface SmokeMetric {
  metric_name: string;
  metric_value: number | null;
  unit: string | null;
  scorer_name: string;
  artifact_sha256: string;
}

interface SmokeCandidate {
  candidate_id: string;
  sequence: string;
  length: number;
  source_model_id: string;
  source_run_id: string;
  input_target: string;
  candidate_class: string;
  source_round: string;
  not_for_primary_ranking: number;
  not_for_wetlab_shortlist: number;
  source_job_id: string;
  gate_json_path: string;
  created_at: string;
  promotion_status: string;
  structures: SmokeStructure[];
  metrics: SmokeMetric[];
  d30_scoring?: D30Scoring;
}

interface D30Scoring {
  d30_round: string;
  status: string; // scored | partial_X_of_5 | not_scored
  scorers_succeeded: number;
  scorers_expected: number;
  complex_source: string | null;
  complex_source_label: string | null;
  values: Record<string, { value: number | null; unit: string | null; scorer_name: string }>;
  provenance: Record<string, { metric_id: string; scorer_version: string; scorer_license: string; metric_provenance: string; artifact_sha256: string }>;
  disclosure: string;
}

interface SmokeResponse {
  smoke_candidates: SmokeCandidate[];
  count: number;
  round_counts: Record<string, number>;
  promotion_gate: {
    states: string[];
    current_default: string;
    requires: string;
  };
  not_for_primary_ranking: boolean;
  not_for_wetlab_shortlist: boolean;
  computational_prediction_only: boolean;
  experimental_validation: boolean;
  warning: string;
}

export function D29SmokeCandidateSection() {
  const [data, setData] = useState<SmokeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        "/api/v1/p33u/smoke-candidates?source_round=P33U_D28",
        { cache: "no-store" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data ?? json);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const candidates = data?.smoke_candidates ?? [];

  return (
    <Card className="border-amber-300">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base">
          <FlaskConical className="h-4 w-4" /> D28 EvoBind2 Smoke Candidate (D29 Ingested, D30 Scored)
        </CardTitle>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className="mr-1 h-3 w-3" /> Refresh
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Warning banners */}
        <div className="flex flex-wrap gap-2">
          <Badge className="bg-amber-100 text-amber-800 border-amber-300">
            DEV SMOKE ONLY
          </Badge>
          <Badge className="bg-rose-100 text-rose-800 border-rose-300">
            NOT TOP4
          </Badge>
          <Badge className="bg-purple-100 text-purple-800 border-purple-300">
            requires D30 scoring before promotion
          </Badge>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
          <ShieldAlert className="h-4 w-4" />
          COMPUTATIONAL PREDICTION ONLY / NOT EXPERIMENTALLY VALIDATED
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="h-3 w-3 animate-spin" /> loading D28 smoke candidate...
          </div>
        ) : null}

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            <AlertTriangle className="h-4 w-4" /> {error}
          </div>
        ) : null}

        {/* Candidate display */}
        {candidates.length > 0 ? (
          <div className="space-y-2">
            {candidates.map((c) => (
              <div
                key={c.candidate_id}
                className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-lg font-bold">
                    {c.sequence}
                  </span>
                  <Badge variant="outline">{c.source_model_id}</Badge>
                  <Badge variant="outline">{c.length}aa</Badge>
                  <Badge
                    className={
                      c.promotion_status === "reviewed_challenger"
                        ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                        : c.promotion_status === "promoted_candidate"
                        ? "bg-green-100 text-green-800 border-green-300"
                        : c.promotion_status === "rejected"
                        ? "bg-rose-100 text-rose-800 border-rose-300"
                        : "bg-slate-200 text-slate-700"
                    }
                  >
                    promotion: {c.promotion_status}
                  </Badge>
                </div>
                <div className="mt-2 text-xs text-slate-600">
                  <div>candidate_id: {c.candidate_id}</div>
                  <div>source_round: {c.source_round}</div>
                  <div>input_target: {c.input_target}</div>
                </div>
                {/* Metrics */}
                <div className="mt-2 grid gap-1 sm:grid-cols-3">
                  {c.metrics.map((m) => (
                    <div
                      key={m.metric_name}
                      className="rounded border border-slate-200 bg-white p-1.5 text-xs"
                    >
                      <span className="font-semibold">{m.metric_name}</span>
                      {m.metric_value != null ? (
                        <span className="ml-1">
                          {m.metric_value.toFixed(4)} {m.unit ?? ""}
                        </span>
                      ) : (
                        <span className="ml-1 text-slate-400">N/A</span>
                      )}
                    </div>
                  ))}
                </div>
                {/* Structure */}
                {c.structures.map((s) => (
                  <div
                    key={s.structure_id}
                    className="mt-2 text-xs text-slate-600"
                  >
                    structure: {s.structure_model} | sha256:{" "}
                    {s.artifact_sha256.slice(0, 16)}...
                  </div>
                ))}
                {/* D30 Unified Scoring (challenger review) */}
                {c.d30_scoring && c.d30_scoring.status !== "not_scored" ? (
                  <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-2.5 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge className="bg-blue-100 text-blue-800 border-blue-300">
                        D30 Unified Scoring
                      </Badge>
                      <Badge
                        className={
                          c.d30_scoring.status === "scored"
                            ? "bg-emerald-100 text-emerald-800 border-emerald-300"
                            : "bg-amber-100 text-amber-800 border-amber-300"
                        }
                      >
                        {c.d30_scoring.scorers_succeeded}/{c.d30_scoring.scorers_expected} scorers
                      </Badge>
                      <span className="text-slate-600">
                        complex_source: {c.d30_scoring.complex_source ?? "n/a"}
                      </span>
                    </div>
                    <div className="mt-2 grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(c.d30_scoring.values).map(([mname, mv]) => (
                        <div
                          key={mname}
                          className="rounded border border-slate-200 bg-white p-1.5"
                        >
                          <span className="font-semibold">{mname}</span>
                          {mv.value != null ? (
                            <span className="ml-1">
                              {Number(mv.value).toFixed(4)} {mv.unit ?? ""}
                            </span>
                          ) : (
                            <span className="ml-1 text-slate-400">unavailable</span>
                          )}
                          <div className="text-[10px] text-slate-400">
                            {mv.scorer_name}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 text-[11px] italic text-slate-500">
                      {c.d30_scoring.disclosure}
                    </div>
                    {c.d30_scoring.complex_source_label ? (
                      <div className="mt-1 text-[11px] text-slate-500">
                        {c.d30_scoring.complex_source_label}
                      </div>
                    ) : null}
                    <details className="mt-1 text-[11px] text-slate-500">
                      <summary className="cursor-pointer">provenance</summary>
                      <div className="mt-1 space-y-0.5">
                        {Object.entries(c.d30_scoring.provenance).map(([mname, pv]) => (
                          <div key={mname}>
                            <span className="font-mono">{pv.metric_id}</span> |{" "}
                            {pv.scorer_version} | {pv.scorer_license} | sha:{" "}
                            {pv.artifact_sha256?.slice(0, 16) ?? "n/a"}...
                          </div>
                        ))}
                      </div>
                    </details>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {/* Promotion gate info */}
        {data?.promotion_gate ? (
          <details className="rounded-md border border-slate-200 bg-white p-2 text-xs">
            <summary className="cursor-pointer font-medium">
              Promotion Gate
            </summary>
            <div className="mt-2 space-y-1 text-slate-600">
              <div>
                States: {data.promotion_gate.states.join(" → ")}
              </div>
              <div>
                Current default: {data.promotion_gate.current_default}
              </div>
              <div>
                Requires: {data.promotion_gate.requires}
              </div>
            </div>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}
