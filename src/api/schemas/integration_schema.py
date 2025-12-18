from pydantic import BaseModel, UUID4, Field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


class AuthTypeEnum(str, Enum):
    BASIC_AUTH = "basic_auth"
    API_TOKEN = "api_token"
    OAUTH2 = "oauth2"


class IntegrationBase(BaseModel):
    service_name: str
    auth_type: AuthTypeEnum
    config: Dict
    is_active: bool


class IntegrationCreate(IntegrationBase):
    status: str = Field(default="success")
    

class IntegrationUpdate(BaseModel):
    status: str = Field(default="success")
    auth_type: Optional[AuthTypeEnum] = None
    config: Optional[Dict] = None
    is_active: Optional[bool] = None


class IntegrationToggleResponse(BaseModel):
    status: str = Field(default="success")
    id: UUID4
    is_active: bool


class IntegrationResponse(BaseModel):
    id: UUID4
    service_name: str
    auth_type: AuthTypeEnum
    config: Dict
    is_active: bool
    last_synced_at: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_error: Optional[str]
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    status: str = Field(default="success")
    integrations: list[IntegrationResponse]