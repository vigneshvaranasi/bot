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


# ==================== Direct User Permission Schemas ====================

class UserDirectPermissionAssignment(BaseModel):
    """Request to assign a permission directly to a user."""
    permission_id: UUID4


class UserDirectPermissionsUpdate(BaseModel):
    """Request to replace all direct permissions for a user."""
    permission_ids: List[UUID4]


class UserDirectPermissionResponse(BaseModel):
    """Response for a direct user permission assignment."""
    permission_id: UUID4
    permission_code: str
    permission_name: str
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[UUID4] = None


class UserDirectPermissionsResponse(BaseModel):
    """Response listing all direct permissions for a user."""
    status: str = Field(default="success")
    user_id: UUID4
    direct_permissions: List[UserDirectPermissionResponse]


# ==================== Direct User Permission Set Schemas ====================

class UserDirectPermissionSetAssignment(BaseModel):
    """Request to assign a permission set directly to a user."""
    permission_set_id: UUID4


class UserDirectPermissionSetsUpdate(BaseModel):
    """Request to replace all direct permission sets for a user."""
    permission_set_ids: List[UUID4]


class UserDirectPermissionSetResponse(BaseModel):
    """Response for a direct user permission set assignment."""
    permission_set_id: UUID4
    permission_set_code: str
    permission_set_name: str
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[UUID4] = None


class UserDirectPermissionSetsResponse(BaseModel):
    """Response listing all direct permission sets for a user."""
    status: str = Field(default="success")
    user_id: UUID4
    direct_permission_sets: List[UserDirectPermissionSetResponse]


# ==================== Effective Permissions Detailed Schemas ====================

class UserEffectivePermissionsDetailedResponse(BaseModel):
    """Response showing effective permissions with breakdown by source."""
    status: str = Field(default="success")
    user_id: UUID4
    from_roles: List[str]  # Permission codes from role assignments
    from_direct_sets: List[str]  # Permission codes from direct permission set assignments
    from_direct_permissions: List[str]  # Permission codes from direct permission assignments
    effective: List[str]  # Union of all (deduplicated)


# ==================== RBAC Audit Log Schemas ====================

class RbacAuditLogResponse(BaseModel):
    """Response for a single RBAC audit log entry."""
    id: UUID4
    entity_type: str
    entity_id: UUID4
    secondary_entity_id: Optional[UUID4] = None
    action: str
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    changed_by: Optional[UUID4] = None
    changed_at: datetime
    ip_address: Optional[str] = None


class RbacAuditLogsResponse(BaseModel):
    """Response listing RBAC audit logs."""
    status: str = Field(default="success")
    audit_logs: List[RbacAuditLogResponse]
    total: int
    limit: int
    offset: int
