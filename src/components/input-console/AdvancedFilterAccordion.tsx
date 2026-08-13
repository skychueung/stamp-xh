import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export function AdvancedFilterAccordion() {
  const params = usePeptideFilterStore((s) => s.params);
  const setParams = usePeptideFilterStore((s) => s.setParams);

  return (
    <Accordion type="single" collapsible defaultValue="filters">
      <AccordionItem value="filters" className="border-0">
        <AccordionTrigger className="text-sm font-medium text-slate-700 hover:no-underline py-3">
          Advanced Filters / 高级筛选
        </AccordionTrigger>
        <AccordionContent>
          <div className="space-y-4 pt-1">
            {/* Length */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">Length Min</Label>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={params.lenMin}
                  onChange={(e) => setParams({ lenMin: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Length Max</Label>
                <Input
                  type="number"
                  min={1}
                  max={200}
                  value={params.lenMax}
                  onChange={(e) => setParams({ lenMax: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
            </div>

            {/* Charge */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">Charge Min</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.chargeMin}
                  onChange={(e) => setParams({ chargeMin: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Charge Max</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.chargeMax}
                  onChange={(e) => setParams({ chargeMax: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
            </div>

            {/* GRAVY */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">GRAVY Min</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.gravyMin}
                  onChange={(e) => setParams({ gravyMin: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">GRAVY Max</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.gravyMax}
                  onChange={(e) => setParams({ gravyMax: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
            </div>

            {/* pI */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-slate-500">pI Min</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.piMin}
                  onChange={(e) => setParams({ piMin: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
              <div>
                <Label className="text-xs text-slate-500">pI Max</Label>
                <Input
                  type="number"
                  step={0.1}
                  value={params.piMax}
                  onChange={(e) => setParams({ piMax: Number(e.target.value) })}
                  className="mt-1 rounded-lg border-slate-200"
                />
              </div>
            </div>

            {/* Cys Max */}
            <div>
              <Label className="text-xs text-slate-500">Cysteine Max</Label>
              <Input
                type="number"
                min={0}
                max={50}
                value={params.cysMax}
                onChange={(e) => setParams({ cysMax: Number(e.target.value) })}
                className="mt-1 rounded-lg border-slate-200"
              />
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
