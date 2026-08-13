import { useCallback, useState } from "react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { checkApiHealth, runPrediction } from "@/lib/api";
export function usePredictionRun() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const params = usePeptideFilterStore((s) => s.params);
  const setStatus = usePeptideFilterStore((s) => s.setStatus);
  const setErrorMessage = usePeptideFilterStore((s) => s.setErrorMessage);
  const setPredictionResult = usePeptideFilterStore((s) => s.setPredictionResult);

  const run = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setStatus("warming");

    try {
      // Check API health first
      const isHealthy = await checkApiHealth();

      if (!isHealthy) {
        throw new Error("API health check failed: /api/health is not reachable");
      }

      setStatus("loading");
      const result = await runPrediction(params);
      setPredictionResult(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "An unknown error occurred";
      setError(msg);
      setErrorMessage(msg);
      setStatus("error");
    } finally {
      setIsRunning(false);
    }
  }, [params, setStatus, setErrorMessage, setPredictionResult]);

  return { run, isRunning, error };
}
