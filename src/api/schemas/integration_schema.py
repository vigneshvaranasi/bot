from pydantic import BaseModel
from enum import Enum


class AuthTypeEnum(str, Enum):
    BASIC_AUTH = "basic_auth"
    API_TOKEN = "api_token"
    OAUTH2 = "oauth2"
    PAT = "pat"


class IntegrationBase(BaseModel):
    service_name: str
    connector_type: str | None = None
    auth_type: AuthTypeEnum
    config: dict
    is_active: bool


class IntegrationCreate(IntegrationBase):
    pass
