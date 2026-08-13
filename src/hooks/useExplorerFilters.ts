import { useState, useMemo } from "react";
import type { Candidate } from "@/types";

type SortField = "rank" | "priorityScore" | "length" | "disulfideRisk";
type SortDir = "asc" | "desc";

export type ExplorerFilters = {
  search: string;
  sortField: SortField;
  sortDir: SortDir;
  riskFilter: string | null;
};

export function useExplorerFilters(candidates: Candidate[]) {
  const [filters, setFilters] = useState<ExplorerFilters>({
    search: "",
    sortField: "rank",
    sortDir: "asc",
    riskFilter: null,
  });

  const filtered = useMemo(() => {
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
  }, [candidates, filters]);

  return { filters, setFilters, filtered };
}
