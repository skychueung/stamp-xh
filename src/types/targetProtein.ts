export interface TargetProtein {
  id: string;
  project_id: string;
  name: string;
  sequence: string;
  sequence_hash: string;
  organism?: string;
  source_type: string;
  length: number;
  metadata_json?: any;
  created_at: string;
  updated_at: string;
}

export type TargetProteinCreate = Omit<TargetProtein, 'id' | 'length' | 'created_at' | 'updated_at'>;
