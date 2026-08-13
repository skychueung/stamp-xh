/**
 * STAMP v1.2 — File Asset Types
 * Mirrors backend/app/routers/file_assets.py schemas
 */

export interface FileAsset {
  asset_id: string;
  file_type: string;
  original_filename: string;
  size_bytes: number;
  sha256: string | null;
}

export interface FileAssetListResponse {
  items: FileAsset[];
  total: number;
}
