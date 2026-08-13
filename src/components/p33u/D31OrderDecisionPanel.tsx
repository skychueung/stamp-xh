import { useEffect, useState } from 'react';
import { RefreshCw, ShieldAlert, ClipboardList, FlaskConical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { p33uApi, type P33UD31OrderDecisions, type P33UD31OrderDecision } from '@/lib/api/p33u';

const DECISION_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  APPROVE_FOR_QUOTE: { bg: 'bg-emerald-200', text: 'text-emerald-900', label: 'APPROVE_FOR_QUOTE' },
  HOLD_AS_REVIEWED_CHALLENGER: { bg: 'bg-amber-200', text: 'text-amber-900', label: 'HOLD_AS_REVIEWED_CHALLENGER' },
  HOLD_NOT_FIRST_ROUND: { bg: 'bg-slate-200', text: 'text-slate-700', label: 'HOLD_NOT_FIRST_ROUND' },
  NOT_FOR_FIRST_ROUND: { bg: 'bg-slate-200', text: 'text-slate-500', label: 'NOT_FOR_FIRST_ROUND' },
};

function DecisionRow({ d, rank }: { d: P33UD31OrderDecision; rank?: number }) {
  const st = DECISION_STYLE[d.order_decision] ?? DECISION_STYLE.NOT_FOR_FIRST_ROUND;
  return (
    <div className="rounded border border-slate-200 bg-white p-2">
      <div className="flex flex-wrap items-center gap-2">
        {rank !== undefined && (
          <Badge className="bg-blue-200 text-blue-900 text-[10px]">#{rank}</Badge>
        )}
        <span className="font-mono text-[11px] font-semibold text-slate-900">{d.candidate_id}</span>
        <Badge className={`${st.bg} ${st.text} text-[10px]`}>{st.label}</Badge>
        <Badge className="bg-rose-100 text-rose-700 text-[9px]">order_status: {d.order_status}</Badge>
        <Badge className="bg-rose-100 text-rose-700 text-[9px]">exp_validated: {String(d.experimental_validation)}</Badge>
        {d.pending_order && (
          <Badge className="bg-orange-100 text-orange-800 text-[9px]">pending_order: true</Badge>
        )}
      </div>
      <p className="mt-1 text-[10px] text-slate-600">{d.reason}</p>
      {d.risk_flags && (
        <p className="mt-1 text-[10px] text-rose-700">
          <span className="font-semibold">risk_flags:</span> {d.risk_flags}
        </p>
      )}
      {d.synthesis_spec && (
        <div className="mt-1 rounded bg-slate-50 p-1.5 text-[10px] text-slate-700">
          <div className="font-semibold text-slate-800">synthesis_spec (round-1, uniform):</div>
          <div>
            purity ≥{d.synthesis_spec.purity_hplc_min} HPLC · {d.synthesis_spec.amount_mg} mg ·{' '}
            {d.synthesis_spec.salt_form} · {d.synthesis_spec.n_terminus} / {d.synthesis_spec.c_terminus} ·{' '}
            {d.synthesis_spec.cyclization} · {d.synthesis_spec.label}
          </div>
          <div className="text-slate-500">storage: {d.synthesis_spec.storage}</div>
          <div className="text-slate-500">delivery: {d.synthesis_spec.delivery_docs}</div>
        </div>
      )}
      {d.validation_plan && (
        <div className="mt-1 text-[10px] text-slate-600">
          <span className="font-semibold">validation_plan:</span> {d.validation_plan}
        </div>
      )}
    </div>
  );
}

export function D31OrderDecisionPanel() {
  const [data, setData] = useState<P33UD31OrderDecisions | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setData(await p33uApi.getD31OrderDecisions());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="rounded-md border border-emerald-300 bg-emerald-50/40 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-emerald-700" />
          <span className="text-xs font-semibold text-emerald-900">
            P33U-D31 Wet-lab Ordering Decision Freeze (Top4 + EvoBind2 challenger)
          </span>
          <Badge className="bg-emerald-200 text-emerald-800 text-[10px]">
            {data?.d31_round ?? 'P33U_D31'}
          </Badge>
          <Badge className="bg-rose-100 text-rose-700 text-[9px]">all order_status: not_ordered</Badge>
          <Badge className="bg-rose-100 text-rose-700 text-[9px]">all experimental_validation: false</Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={'h-3 w-3 ' + (loading ? 'animate-spin' : '')} /> reload
        </Button>
      </div>

      {error && <p className="mt-2 text-[11px] text-red-700">load error: {error}</p>}

      <div className="mt-2 flex items-start gap-1.5 rounded bg-amber-50 p-1.5">
        <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />
        <p className="text-[10px] text-amber-800">
          {data?.disclosure ??
            'All candidates COMPUTATIONAL_PREDICTION_ONLY / NOT_EXPERIMENTALLY_VALIDATED. No order placed. Top4 authority frozen by D15/D18/D19D/D27; D26 proposal does NOT overwrite frozen Top4. PPFlow blocked_license (never run).'}
        </p>
      </div>

      {data && (
        <>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge className="bg-emerald-200 text-emerald-900 text-[10px]">
              APPROVE_FOR_QUOTE: {data.decision_counts?.APPROVE_FOR_QUOTE ?? 4}
            </Badge>
            <Badge className="bg-amber-200 text-amber-900 text-[10px]">
              HOLD_AS_REVIEWED_CHALLENGER: {data.decision_counts?.HOLD_AS_REVIEWED_CHALLENGER ?? 1}
            </Badge>
            <Badge className="bg-slate-200 text-slate-700 text-[10px]">
              HOLD_NOT_FIRST_ROUND: {data.decision_counts?.HOLD_NOT_FIRST_ROUND ?? 5}
            </Badge>
            <Badge className="bg-slate-200 text-slate-500 text-[10px]">
              NOT_FOR_FIRST_ROUND: {data.decision_counts?.NOT_FOR_FIRST_ROUND ?? 22}
            </Badge>
          </div>

          <div className="mt-2">
            <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-emerald-900">
              <FlaskConical className="h-3 w-3" />
              Top4 — APPROVE_FOR_QUOTE (pending_order=true, order_status=not_ordered)
            </div>
            <div className="space-y-1.5">
              {data.top4.map((d, i) => (
                <DecisionRow key={d.candidate_id} d={d} rank={i + 1} />
              ))}
            </div>
          </div>

          <div className="mt-2">
            <div className="mb-1 text-[11px] font-semibold text-amber-900">
              D28 EvoBind2 Challenger — HOLD_AS_REVIEWED_CHALLENGER (round-2 reserve)
            </div>
            <DecisionRow d={data.challenger} />
          </div>

          <div className="mt-2">
            <div className="mb-1 text-[11px] font-semibold text-slate-700">
              Other 12aa primary — HOLD_NOT_FIRST_ROUND (round-2 reserve)
            </div>
            <div className="space-y-1.5">
              {data.hold_not_first_round.map((d) => (
                <DecisionRow key={d.candidate_id} d={d} />
              ))}
            </div>
          </div>

          <p className="mt-2 text-[10px] text-slate-500">
            22aa deviation / dev_smoke_candidate / PPFlow (blocked_license) / 9-10aa candidates =
            NOT_FOR_FIRST_ROUND (not shown individually). {data.ppflow_status}. {data.warning}
          </p>
        </>
      )}
    </div>
  );
}
