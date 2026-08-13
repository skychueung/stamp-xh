import type { FilterParams } from "@/types";

export type PresetConfig = {
  name: string;
  description: string;
  params: Partial<FilterParams>;
};

const PRESETS: Record<string, PresetConfig> = {
  balanced: {
    name: "Balanced / 均衡",
    description: "Default balanced weighting across all properties",
    params: {
      disulfideWeight: 0.25,
      chargeWeight: 0.25,
      hydrophobicityWeight: 0.25,
      piWeight: 0.25,
    },
  },
  "charge-prioritized": {
    name: "Charge-prioritized / 电荷优先",
    description: "Prioritize charge properties in ranking",
    params: {
      disulfideWeight: 0.15,
      chargeWeight: 0.40,
      hydrophobicityWeight: 0.25,
      piWeight: 0.20,
    },
  },
  "hydrophobicity-focused": {
    name: "Hydrophobicity-focused / 疏水性聚焦",
    description: "Focus on hydrophobicity characteristics",
    params: {
      disulfideWeight: 0.15,
      chargeWeight: 0.20,
      hydrophobicityWeight: 0.40,
      piWeight: 0.25,
    },
  },
  "disulfide-safe": {
    name: "Disulfide-safe / 二硫化物安全",
    description: "Maximize disulfide bond safety",
    params: {
      disulfideWeight: 0.40,
      chargeWeight: 0.20,
      hydrophobicityWeight: 0.20,
      piWeight: 0.20,
    },
  },
};

export function getPreset(name: string): PresetConfig | undefined {
  return PRESETS[name];
}

export function getAllPresets(): { key: string; name: string; description: string }[] {
  return Object.entries(PRESETS).map(([key, config]) => ({
    key,
    name: config.name,
    description: config.description,
  }));
}

export { PRESETS };
