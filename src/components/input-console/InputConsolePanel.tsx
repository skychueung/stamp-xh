import { Terminal } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { BasicInputForm } from "./BasicInputForm";
import { AdvancedFilterAccordion } from "./AdvancedFilterAccordion";
import { RankingWeightsAccordion } from "./RankingWeightsAccordion";
import { PresetSelector } from "./PresetSelector";
import { RunActions } from "./RunActions";

export function InputConsolePanel() {
  return (
    <Card className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <CardHeader className="p-0 mb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Terminal className="h-5 w-5 text-slate-600" />
          Input Console
        </CardTitle>
        <p className="text-sm text-slate-600 mt-1">
          Configure input sequence and filtering parameters
        </p>
      </CardHeader>
      <CardContent className="p-0 space-y-4">
        <BasicInputForm />
        <Separator className="my-2" />
        <AdvancedFilterAccordion />
        <Separator className="my-2" />
        <RankingWeightsAccordion />
        <Separator className="my-2" />
        <PresetSelector />
        <Separator className="my-2" />
        <RunActions />
      </CardContent>
    </Card>
  );
}
