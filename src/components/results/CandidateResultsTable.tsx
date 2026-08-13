import { useState, useMemo, useCallback } from "react";
import { Search, Table2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExplorerToolbar, type ExplorerFilterState } from "@/components/candidates/ExplorerToolbar";
import { CandidateTable, CandidateTableSkeleton } from "@/components/candidates/CandidateTable";
import type { Candidate } from "@/types";

function filterAndSortCandidates(
  candidates: Candidate[],
  filters: ExplorerFilterState
): Candidate[] {
  let result = [...candidates];

  if (filters.search.trim()) {
    const q = filters.search.toUpperCase();
    result = result.filter((c) => c.sequence.toUpperCase().includes(q));
  }

  if (filters.riskFilter) {
    result = result.filter((c) => c.disulfideRisk === filters.riskFilter);
  }

  result.sort((a, b) => {
    const dir = filters.sortDir === "asc" ? 1 : -1;
    switch (filters.sortField) {
      case "rank":
        return (a.rank - b.rank) * dir;
      case "priorityScore":
        return (a.priorityScore - b.priorityScore) * dir;
      case "length":
        return (a.length - b.length) * dir;
      case "disulfideRisk": {
        const riskOrder = { low: 0, medium: 1, high: 2, unknown: 3 };
        return ((riskOrder[a.disulfideRisk] ?? 3) - (riskOrder[b.disulfideRisk] ?? 3)) * dir;
      }
      default:
        return (a.rank - b.rank) * dir;
    }
  });

  return result;
}

function candidatesToCSV(candidates: Candidate[]): string {
  const headers = [
    "Rank", "Sequence", "Length", "Priority Score", "Disulfide Score",
    "Charge Score", "Hydrophobicity Score", "pI Score", "Net Charge",
    "GRAVY", "pI", "Cys Count", "Disulfide Risk",
  ];
  const rows = candidates.map((c) => [
    c.rank, c.sequence, c.length, c.priorityScore, c.disulfideScore,
    c.chargeScore, c.hydrophobicityScore, c.pIScore, c.netCharge,
    c.gravy, c.pI, c.cysCount, c.disulfideRisk,
  ]);
  return [headers, ...rows].map((r) => r.join(",")).join("\n");
}

type CandidateResultsTableProps = {
  candidates: Candidate[];
  status: "idle" | "loading" | "success" | "error" | "warming";
};

export function CandidateResultsTable({ candidates, status }: CandidateResultsTableProps) {
  const [filters, setFilters] = useState<ExplorerFilterState>({
    search: "",
    sortField: "rank",
    sortDir: "asc",
    riskFilter: null,
  });

  const filtered = useMemo(() => filterAndSortCandidates(candidates, filters), [candidates, filters]);

  const handleExport = useCallback(() => {
    const csv = candidatesToCSV(filtered);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "candidates.csv";
    a.click();
    URL.revokeObjectURL(url);
  }, [filtered]);

  const isEmptyResult = status === "success" && candidates.length === 0;
  const showSkeleton = status === "loading";
  const showIdle = status === "idle";

  return (
    <Card className="rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col min-h-[480px]">
      <CardHeader className="p-5 pb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Table2 className="h-5 w-5 text-slate-600" />
          Candidate Results
        </CardTitle>
        <p className="text-sm text-slate-600 mt-1">
          全量候选肽段结果，支持搜索、排序、筛选与导出
        </p>
      </CardHeader>
      <CardContent className="p-5 pt-0 space-y-4 flex-1 flex flex-col min-h-0">
        <ExplorerToolbar
          filters={filters}
          onChange={setFilters}
          resultCount={filtered.length}
          onExport={handleExport}
        />

        {showSkeleton && <CandidateTableSkeleton />}

        {showIdle && (
          <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 mb-3">
              <Search className="h-6 w-6 text-slate-400" />
            </div>
            <h3 className="text-sm font-semibold text-slate-700">等待开始</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              运行预测后，全量结果将在此展示
            </p>
          </div>
        )}

        {isEmptyResult && (
          <div className="flex flex-col items-center justify-center py-16 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 mb-3">
              <Search className="h-6 w-6 text-slate-400" />
            </div>
            <h3 className="text-sm font-semibold text-slate-700">未筛选到符合条件的候选</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              后端返回成功，但未找到符合条件的候选肽段，请放宽筛选条件重试。
            </p>
          </div>
        )}

        {!showSkeleton && !showIdle && !isEmptyResult && (
          <div className="flex-1 overflow-auto min-h-0">
            <CandidateTable candidates={filtered} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
