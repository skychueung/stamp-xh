import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { getAllPresets, getPreset } from "@/lib/presets";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

export function PresetSelector() {
  const setParams = usePeptideFilterStore((s) => s.setParams);
  const presets = getAllPresets();

  const handlePresetChange = (key: string) => {
    const config = getPreset(key);
    if (config?.params) {
      setParams(config.params);
    }
  };

  return (
    <div>
      <Label htmlFor="preset-select" className="text-sm font-medium text-slate-700">
        Preset / 预设配置
      </Label>
      <Select onValueChange={handlePresetChange}>
        <SelectTrigger className="mt-1.5 rounded-lg border-slate-200 bg-white">
          <SelectValue placeholder="选择预设配置..." />
        </SelectTrigger>
        <SelectContent>
          {presets.map((preset) => (
            <SelectItem key={preset.key} value={preset.key}>
              {preset.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
