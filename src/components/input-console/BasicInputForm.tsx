import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SEQUENCE_PLACEHOLDER =
  "Enter amino acid sequence (e.g., MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGE...)";

export function BasicInputForm() {
  const params = usePeptideFilterStore((s) => s.params);
  const setParams = usePeptideFilterStore((s) => s.setParams);

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="protein-name" className="text-sm font-medium text-slate-700">
          Protein Name / 蛋白名称
        </Label>
        <Input
          id="protein-name"
          value={params.proteinName}
          onChange={(e) => setParams({ proteinName: e.target.value })}
          placeholder="Enter protein name"
          className="mt-1.5 rounded-lg border-slate-200 focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
        />
      </div>

      <div>
        <Label htmlFor="protein-sequence" className="text-sm font-medium text-slate-700">
          Protein Sequence / 蛋白序列
        </Label>
        <Textarea
          id="protein-sequence"
          value={params.proteinSequence}
          onChange={(e) => setParams({ proteinSequence: e.target.value })}
          placeholder={SEQUENCE_PLACEHOLDER}
          className="mt-1.5 min-h-[120px] rounded-lg border-slate-200 font-mono text-sm focus:border-slate-400 focus:ring-2 focus:ring-slate-100 resize-y"
        />
        <p className="mt-1 text-xs text-slate-400">
          {params.proteinSequence.length > 0
            ? `${params.proteinSequence.replace(/\s/g, "").length} residues`
            : "Paste a protein sequence in FASTA or plain text format"}
        </p>
      </div>

      <div>
        <Label htmlFor="candidate-count" className="text-sm font-medium text-slate-700">
          Candidate Count / 候选数量
        </Label>
        <Select
          value={String(params.candidateCount)}
          onValueChange={(v) => setParams({ candidateCount: Number(v) })}
        >
          <SelectTrigger className="mt-1.5 rounded-lg border-slate-200 bg-white">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="60">60</SelectItem>
            <SelectItem value="120">120</SelectItem>
            <SelectItem value="200">200</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
