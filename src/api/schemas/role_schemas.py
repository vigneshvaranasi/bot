from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID


class RoleCreate(BaseModel):
    """Schema for creating a new role."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permission_set_ids: Optional[List[UUID]] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Schema for updating an existing role."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permission_set_ids: Optional[List[UUID]] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class RoleDetailResponse(BaseModel):
    """Response with permission set details."""
    id: str
    name: str
    description: Optional[str] = None
    permission_sets: List[dict] = []