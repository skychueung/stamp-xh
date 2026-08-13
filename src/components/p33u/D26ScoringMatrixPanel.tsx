import { useEffect, useState } from 'react';
import { RefreshCw, ShieldAlert, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { p33uApi, type P33UD26ScoringMatrix, type P33UD26Candidate } from '@/lib/api/p33u';

const MODEL_LABELS: Record<string, string> = {
  pepmlm: 'PepMLM',
  evobind2: 'EvoBind2',
  diffpepbuilder: 'DiffPepBuilder',
  pephar: 'PepHAR',
};

function fmt(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return '—';
  return Number(v).toFixed(digits);
}

export function D26ScoringMatrixPanel() {
  const [matrix, setMatrix] = useState<P33UD26ScoringMatrix | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setMatrix(await p33uApi.getD26ScoringMatrix());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'fetch failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const cands = matrix?.candidates ?? [];
  // sort by proposal rank
  const sorted = [...cands].sort((a, b) => (a.d26_proposal_rank ?? 99) - (b.d26_proposal_rank ?? 99));

  return (
    <div className="rounded-md border border-blue-300 bg-blue-50/40 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Table2 className="h-4 w-4 text-blue-700" />
          <span className="text-xs font-semibold text-blue-900">
            P33U-D26 Unified Scoring Matrix (9 true 12aa · page/API batch)
          </span>
          <Badge className="bg-blue-200 text-blue-800 text-[10px]">{matrix?.round ?? 'P33U_D26'}</Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={'h-3 w-3 ' + (loading ? 'animate-spin' : '')} /> reload
        </Button>
      </div>

      {error && (
        <p className="mt-2 text-[11px] text-red-700">load error: {error}</p>
      )}

      {matrix && (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Badge className="bg-emerald-200 text-emerald-800 text-[10px]">{matrix.gate}</Badge>
            <span className="text-[11px] text-slate-700">{matrix.ranking_rule}</span>
          </div>
          <div className="mt-1.5 flex items-start gap-1.5 rounded bg-amber-50 p-1.5">
            <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />
            <p className="text-[10px] leading-tight text-amber-800">{matrix.honesty_disclaimer}</p>
          </div>
          <p className="mt-1 text-[10px] italic text-slate-600">{matrix.frozen_top4_disclaimer}</p>

          {/* Scoring matrix table */}
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead className="text-slate-700">
                <tr className="text-left bg-slate-100">
                  <th className="py-1 pr-2">#</th>
                  <th className="py-1 pr-2">candidate</th>
                  <th className="py-1 pr-2">model</th>
                  <th className="py-1 pr-2">complex_source</th>
                  <th className="py-1 pr-2 text-right">PRODIGY ΔG</th>
                  <th className="py-1 pr-2 text-right">Vina pose</th>
                  <th className="py-1 pr-2 text-right">OpenMM (before→after)</th>
                  <th className="py-1 pr-2 text-right">MM-GBSA ΔG</th>
                  <th className="py-1 pr-2 text-right">AF2 pLDDT</th>
                  <th className="py-1 pr-2 text-right">AF2 ipTM</th>
                  <th className="py-1 pr-2">D15/D18 rank</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((c: P33UD26Candidate) => {
                  const isTop4 = c.d15_d18_top4_rank !== null;
                  return (
                    <tr key={c.candidate_id} className={'border-t border-slate-200 align-top ' + (isTop4 ? 'bg-blue-50/60' : '')}>
                      <td className="py-1 pr-2 font-semibold text-blue-700">{c.d26_proposal_rank}</td>
                      <td className="py-1 pr-2 font-mono text-[9px]">{c.candidate_id}</td>
                      <td className="py-1 pr-2">{MODEL_LABELS[c.model] ?? c.model}</td>
                      <td className="py-1 pr-2">
                        <Badge className={'text-[9px] ' + (c.complex_source === 'EXISTING_AF2_COMPLEX' ? 'bg-purple-200 text-purple-800' : 'bg-amber-200 text-amber-800')}>
                          {c.complex_source === 'EXISTING_AF2_COMPLEX' ? 'AF2' : 'PLACEMENT'}
                        </Badge>
                      </td>
                      <td className="py-1 pr-2 text-right font-mono">{fmt(c.scores.prodigy.delta_g_kcal_mol, 1)}</td>
                      <td className="py-1 pr-2 text-right font-mono">{fmt(c.scores.vina.pose_score_kcal_mol, 3)}</td>
                      <td className="py-1 pr-2 text-right font-mono text-[9px]">
                        {fmt(c.scores.openmm.initial_energy_kj_mol, 0)}→{fmt(c.scores.openmm.final_energy_kj_mol, 0)}
                      </td>
                      <td className="py-1 pr-2 text-right font-mono">{fmt(c.scores.mmgbsa.delta_g_kcal_mol, 1)}</td>
                      <td className="py-1 pr-2 text-right font-mono">{fmt(c.scores.af2_multimer.plddt, 1)}</td>
                      <td className="py-1 pr-2 text-right font-mono">{fmt(c.scores.af2_multimer.iptm, 2)}</td>
                      <td className="py-1 pr-2 text-center">{c.d15_d18_top4_rank ?? '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Reranking proposal */}
          <div className="mt-3">
            <div className="flex items-center gap-1.5">
              <Badge className="bg-blue-200 text-blue-800 text-[10px]">RERANKING PROPOSAL</Badge>
              <span className="text-[10px] text-slate-600">proposal only · does NOT overwrite frozen D15/D18 Top4</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {matrix.reranking_proposal.map((r) => {
                const changeColor =
                  r.change === 'same_rank' ? 'bg-emerald-100 text-emerald-700' :
                  r.change === 'reordered_within_top4' ? 'bg-amber-100 text-amber-700' :
                  r.change === 'not_in_d15_top4' ? 'bg-slate-100 text-slate-600' : 'bg-slate-100 text-slate-600';
                return (
                  <span key={r.candidate_id} className={'rounded border px-1.5 py-0.5 text-[9px] ' + changeColor}>
                    #{r.proposal_rank} {r.candidate_id.length > 22 ? r.candidate_id.slice(0, 20) + '…' : r.candidate_id}
                    {r.d15_d18_rank ? ` (D15:${r.d15_d18_rank})` : ''}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Per-score honesty labels */}
          <details className="mt-2 text-[10px] text-slate-600">
            <summary className="cursor-pointer font-semibold text-slate-700">score-type labels (NOT interchangeable)</summary>
            <ul className="mt-1 space-y-0.5 pl-3">
              <li><b>PRODIGY ΔG</b>: predicted binding ΔG (kcal/mol); NOT measured Kd.</li>
              <li><b>Vina pose</b>: pose score of bound placement complex (rigid, NOT docking search, NOT Kd).</li>
              <li><b>OpenMM</b>: 50-step relaxation energy (kJ/mol); NOT binding affinity.</li>
              <li><b>MM-GBSA ΔG</b>: rescoring (igb=2); NOT Kd; positive = unfavorable placement pose.</li>
              <li><b>AF2 pLDDT/ipTM</b>: structural confidence (single_sequence); NOT affinity; pLDDT NOT Kd.</li>
              <li><b>Blocked</b>: gnina=unavailable_with_reason; esmfold=env_present_weights_pending; pyrosetta=blocked_license.</li>
            </ul>
          </details>
        </>
      )}
    </div>
  );
}
