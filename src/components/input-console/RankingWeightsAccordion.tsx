import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export function RankingWeightsAccordion() {
  const params = usePeptideFilterStore((s) => s.params);
  const setParams = usePeptideFilterStore((s) => s.setParams);

  const weights = [
    {
      key: "disulfideWeight" as const,
      label: "Disulfide / 二硫化物",
      value: params.disulfideWeight,
    },
    {
      key: "chargeWeight" as const,
      label: "Charge / 电荷",
      value: params.chargeWeight,
    },
    {
      key: "hydrophobicityWeight" as const,
      label: "Hydrophobicity / 疏水性",
      value: params.hydrophobicityWeight,
    },
    {
      key: "piWeight" as const,
      label: "pI / 等电点",
      value: params.piWeight,
    },
  ];

  const total = weights.reduce((s, w) => s + w.value, 0);

  return (
    <Accordion type="single" collapsible defaultValue="weights">
      <AccordionItem value="weights" className="border-0">
        <AccordionTrigger className="text-sm font-medium text-slate-700 hover:no-underline py-3">
          Ranking Weights / 评分权重
        </AccordionTrigger>
        <AccordionContent>
          <div className="space-y-5 pt-1">
            {weights.map((w) => (
              <div key={w.key}>
                <div className="flex items-center justify-between mb-2">
                  <Label className="text-xs text-slate-500">{w.label}</Label>
                  <span className="text-xs font-mono text-slate-700 tabular-nums">
                    {w.value.toFixed(2)}
                  </span>
                </div>
                <Slider
                  value={[w.value]}
                  min={0}
                  max={1}
                  step={0.01}
                  onValueChange={([v]) => setParams({ [w.key]: v })}
                  className="w-full"
                />
              </div>
            ))}

            {/* Weight distribution bar */}
            <div className="pt-1">
              <div className="flex items-center justify-between mb-1.5">
                <Label className="text-xs text-slate-500">Distribution</Label>
                <span
                  className={`text-xs font-mono tabular-nums ${
                    Math.abs(total - 1) < 0.01 ? "text-emerald-600" : "text-blue-600"
                  }`}
                >
                  Total: {total.toFixed(2)}
                </span>
              </div>
              <div className="flex h-2 rounded-full overflow-hidden bg-slate-100">
                {weights.map((w, i) => {
                  const pct = total > 0 ? (w.value / total) * 100 : 25;
                  const colors = ["bg-teal-500", "bg-blue-500", "bg-violet-500", "bg-blue-500"];
                  return (
                    <div
                      key={w.key}
                      className={`${colors[i]} transition-all duration-300`}
                      style={{ width: `${pct}%` }}
                    />
                  );
                })}
              </div>
              <div className="flex gap-3 mt-2">
                {weights.map((w, i) => {
                  const colors = [
                    "bg-teal-500",
                    "bg-blue-500",
                    "bg-violet-500",
                    "bg-blue-500",
                  ];
                  return (
                    <div key={w.key} className="flex items-center gap-1">
                      <div className={`h-2 w-2 rounded-full ${colors[i]}`} />
                      <span className="text-[10px] text-slate-500">{w.label.split(" / ")[0]}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
