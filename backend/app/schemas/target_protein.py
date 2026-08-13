"""STAMP Platform — Pydantic Schemas for Target Protein."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.project import SchemaBase


class TargetProteinCreate(SchemaBase):
    project_id: str
    name: str = Field(..., max_length=255)
    sequence: str
    sequence_hash: str = Field(..., max_length=64)
    length: int
    organism: Optional[str] = Field(None, max_length=100)
    source_type: str = Field(default="manual", max_length=50)
    uniprot_id: Optional[str] = Field(None, max_length=20)
    pdb_id: Optional[str] = Field(None, max_length=10)
    chain_id: Optional[str] = Field(None, max_length=10)
    metadata_json: Optional[dict] = None


class TargetProteinUpdate(SchemaBase):
    name: Optional[str] = Field(None, max_length=255)
    organism: Optional[str] = Field(None, max_length=100)
    metadata_json: Optional[dict] = None


class TargetProteinResponse(SchemaBase):
    id: str
    project_id: str
    name: str
    sequence: str
    sequence_hash: str
    length: int
    organism: Optional[str]
    source_type: str
    uniprot_id: Optional[str]
    pdb_id: Optional[str]
    chain_id: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime
