export interface EpitopeScan {
  id: string;
  project_id: string;
  target_protein_id: string;
  parameters: Record<string, any>;
  algorithm: string;
  algorithm_version?: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  started_at?: string;
  finished_at?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export type EpitopeScanCreate = Omit<
  EpitopeScan,
  'id' | 'status' | 'started_at' | 'finished_at' | 'error_message' | 'created_at' | 'updated_at'
>;
