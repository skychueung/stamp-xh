import { useState, useMemo, useCallback } from "react";
import { Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { MOCK_CANDIDATES } from "@/lib/constants";
import type { Candidate } from "@/types";
import { ExplorerToolbar } from "./ExplorerToolbar";
import type { ExplorerFilterState } from "./ExplorerToolbar";
import { CandidateTable } from "./CandidateTable";

function filterAndSortCandidates(
  candidates: Candidate[],
  filters: ExplorerFilterState
): Candidate[] {
  let result = [...candidates];

  // Search
  if (filters.search.trim()) {
    const q = filters.search.toUpperCase();
    result = result.filter((c) => c.sequence.toUpperCase().includes(q));
  }

  // Risk filter
  if (filters.riskFilter) {
    result = result.filter((c) => c.disulfideRisk === filters.riskFilter);
  }

  // Sort
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

export function CandidateExplorerSection() {
  const candidates = usePeptideFilterStore((s) => s.candidates);
  const data = candidates.length > 0 ? candidates : MOCK_CANDIDATES;

  const [filters, setFilters] = useState<ExplorerFilterState>({
    search: "",
    sortField: "rank",
    sortDir: "asc",
    riskFilter: null,
  });

  const filtered = useMemo(() => filterAndSortCandidates(data, filters), [data, filters]);

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

  return (
    <Card className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <CardHeader className="p-0 mb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Search className="h-5 w-5 text-slate-600" />
          Candidate Explorer
        </CardTitle>
        <p className="text-sm text-slate-600 mt-1">
          Browse, filter, and export all candidate peptides
        </p>
      </CardHeader>
      <CardContent className="p-0 space-y-4">
        <ExplorerToolbar
          filters={filters}
          onChange={setFilters}
          resultCount={filtered.length}
          onExport={handleExport}
        />
        <CandidateTable candidates={filtered} />
      </CardContent>
    </Card>
  );
}
