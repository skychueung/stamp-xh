import { useCallback } from "react";
import { Play, RotateCcw, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { usePredictionRun } from "@/hooks/usePredictionRun";

const EXAMPLE_SEQUENCE =
  "MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVKLVNEVTEFAKTCVADESAENCDKSLHTLFGDKLCTVATLRETYGEMADCCAKQEPERNECFLQHKDDNPNLPRLVRPEVDVMCTAFHDNEETFLKKYLYEIARRHPYFYAPELLFFAKRYKAAFTECCQAADKAACLLPKLDELRDEGKASSAKQRLKCASLQKFGERAFKAWAVARLSQRFPKAEFAEVSKLVTDLTKVHTECCHGDLLECADDRADLAKYICENQDSISSKLKECCEKPLLEKSHCIAEVENDEMPADLPSLAADFVESKDVCKNYAEAKDVFLGMFLYEYARRHPDYSVVLLLRLAKTYETTLEKCCAAADPHECYAKVFDEFKPLVEEPQNLIKQNCELFEQLGEYKFQNALLVRYTKKVPQVSTPTLVEVSRNLGKVGSKCCKHPEAKRMPCAEDYLSVVLNQLCVLHEKTPVSDRVTKCCTESLVNRRPCFSALTPDETYVPKAFDEKLFTFHADICTLPDTEKQIKKQTALVELLKHKPKATEEQLKTVMENFVAFVDKCCAADDKEACFAVEGPKLVVSTQTALA";

export function RunActions() {
  const { run, isRunning } = usePredictionRun();
  const store = usePeptideFilterStore();
  const status = store.status;
  const setParams = store.setParams;

  const isLoading = isRunning || status === "warming";

  const handleLoadExample = useCallback(() => {
    setParams({
      proteinName: "BSA",
      proteinSequence: EXAMPLE_SEQUENCE,
      candidateCount: 120,
    });
  }, [setParams]);

  const handleReset = useCallback(() => {
    store.resetAll();
  }, [store]);

  return (
    <div className="space-y-3 pt-2">
      <div className="flex gap-2">
        <Button
          variant="outline"
          className="flex-1 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg text-sm font-medium gap-2"
          onClick={handleLoadExample}
        >
          <FileText className="h-4 w-4" />
          Load Example
        </Button>
        <Button
          variant="outline"
          className="flex-1 bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg text-sm font-medium gap-2"
          onClick={handleReset}
        >
          <RotateCcw className="h-4 w-4" />
          Reset
        </Button>
      </div>
      <Button
        className="w-full bg-slate-900 text-white hover:bg-slate-800 rounded-lg py-2.5 text-sm font-medium gap-2"
        onClick={run}
        disabled={isLoading}
      >
        {isLoading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <Play className="h-4 w-4" />
        )}
        Run Prediction
      </Button>
    </div>
  );
}
