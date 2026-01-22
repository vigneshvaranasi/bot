from pydantic import BaseModel, UUID4, Field
from typing import Optional, List
from datetime import datetime


# ==================== Permission Schemas ====================

class PermissionBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    category: str


class PermissionCreate(PermissionBase):
    pass


class PermissionResponse(PermissionBase):
    id: UUID4
    is_system: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PermissionListResponse(BaseModel):
    status: str = Field(default="success")
    permissions: List[PermissionResponse]


class PermissionCategoryResponse(BaseModel):
    status: str = Field(default="success")
    categories: List[str]


# ==================== Permission Set Schemas ====================

class PermissionSetBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None


class PermissionSetCreate(PermissionSetBase):
    permission_codes: List[str]  # List of permission codes to include


class PermissionSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_codes: Optional[List[str]] = None


class PermissionSetResponse(PermissionSetBase):
    id: UUID4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permissions: List[PermissionResponse] = []


class PermissionSetListResponse(BaseModel):
    status: str = Field(default="success")
    permission_sets: List[PermissionSetResponse]


class PermissionSetBriefResponse(BaseModel):
    """Brief response without nested permissions for role responses."""
    id: UUID4
    code: str
    name: str
    description: Optional[str] = None


# ==================== Role Schemas ====================

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    permission_set_codes: List[str]  # List of permission set codes to include


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_set_codes: Optional[List[str]] = None


class RoleResponse(BaseModel):
    id: UUID4
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    permission_sets: List[PermissionSetBriefResponse] = []


class RoleBriefResponse(BaseModel):
    """Brief response for user role assignments."""
    id: UUID4
    name: str
    description: Optional[str] = None


class RoleListResponse(BaseModel):
    status: str = Field(default="success")
    roles: List[RoleResponse]


class RoleEffectivePermissionsResponse(BaseModel):
    """Response showing all effective permissions for a role."""
    status: str = Field(default="success")
    role_id: UUID4
    role_name: str
    permissions: List[str]  # List of permission codes


# ==================== User Role Schemas ====================

class UserRoleAssignment(BaseModel):
    role_id: UUID4


class UserRoleResponse(BaseModel):
    role_id: UUID4
    role_name: str
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[UUID4] = None


class UserRolesResponse(BaseModel):
    status: str = Field(default="success")
    user_id: UUID4
    roles: List[UserRoleResponse]


class UserEffectivePermissionsResponse(BaseModel):
    """Response showing all effective permissions for a user."""
    status: str = Field(default="success")
    user_id: UUID4
    permissions: List[str]  # List of permission codes


# ==================== Bulk Operations ====================

class BulkRoleAssignment(BaseModel):
    user_ids: List[UUID4]
    role_id: UUID4


class BulkRoleAssignmentResponse(BaseModel):
    status: str = Field(default="success")
    assigned_count: int
    failed_count: int
    errors: List[str] = []
