"""STAMP Platform — Pydantic Schemas for Project."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(SchemaBase):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    species: Optional[str] = Field(None, max_length=100)
    project_type: Optional[str] = Field(None, max_length=100)


class ProjectUpdate(SchemaBase):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    species: Optional[str] = Field(None, max_length=100)
    project_type: Optional[str] = Field(None, max_length=100)


class ProjectResponse(SchemaBase):
    id: str
    name: str
    description: Optional[str]
    species: Optional[str]
    project_type: Optional[str]
    created_at: datetime
    updated_at: datetime
