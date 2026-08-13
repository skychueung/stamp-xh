import { Search, Download, Filter } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type SortField = "rank" | "priorityScore" | "length" | "disulfideRisk";
type SortDir = "asc" | "desc";

export type ExplorerFilterState = {
  search: string;
  sortField: SortField;
  sortDir: SortDir;
  riskFilter: string | null;
};

type ExplorerToolbarProps = {
  filters: ExplorerFilterState;
  onChange: (filters: ExplorerFilterState) => void;
  resultCount: number;
  onExport: () => void;
};

const RISK_OPTIONS = [
  { key: null, label: "All" },
  { key: "low", label: "Low" },
  { key: "medium", label: "Medium" },
  { key: "high", label: "High" },
];

export function ExplorerToolbar({ filters, onChange, resultCount, onExport }: ExplorerToolbarProps) {
  return (
    <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
      <div className="flex flex-1 items-center gap-2 w-full sm:w-auto">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search sequence..."
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            className="pl-9 rounded-lg border-slate-200 text-sm"
          />
        </div>
        <Select
          value={`${filters.sortField}-${filters.sortDir}`}
          onValueChange={(v) => {
            const [field, dir] = v.split("-") as [SortField, SortDir];
            onChange({ ...filters, sortField: field, sortDir: dir });
          }}
        >
          <SelectTrigger className="w-[140px] rounded-lg border-slate-200 bg-white text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="rank-asc">Rank (Asc)</SelectItem>
            <SelectItem value="priorityScore-desc">Score (Desc)</SelectItem>
            <SelectItem value="length-asc">Length (Asc)</SelectItem>
            <SelectItem value="disulfideRisk-asc">Risk (Asc)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <Filter className="h-4 w-4 text-slate-400" />
          {RISK_OPTIONS.map((opt) => (
            <Badge
              key={opt.key ?? "all"}
              variant={filters.riskFilter === opt.key ? "default" : "outline"}
              className={`cursor-pointer text-[10px] ${
                filters.riskFilter === opt.key
                  ? "bg-slate-800 text-white hover:bg-slate-700"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
              onClick={() => onChange({ ...filters, riskFilter: opt.key })}
            >
              {opt.label}
            </Badge>
          ))}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="rounded-lg border-slate-200 text-slate-700 hover:bg-slate-50 text-xs gap-1.5"
          onClick={onExport}
        >
          <Download className="h-3.5 w-3.5" />
          Export
        </Button>
      </div>

      <span className="text-xs text-slate-400">{resultCount} results</span>
    </div>
  );
}
