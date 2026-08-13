export type LinkerType = 'none' | 'flexible' | 'rigid' | 'alternative';

export interface LinkerScore {
  id: number;
  peptideSequence: string;
  linkerLength: number;
  flexibility: string;
  score: number;
}

export interface ScoreItem {
  label: string;
  score: number;
  maxScore: number;
  criteria: string[];
}

export interface StampInputState {
  sequence: string;
  advancedOpen: boolean;
}

export interface SidebarNavItem {
  key: string;
  label: string;
  href: string;
}
