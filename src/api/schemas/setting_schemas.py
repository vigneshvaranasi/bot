from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import List
from enum import Enum

class ModelEnum(str, Enum):
    GEMMA3_1B = "gemma3:1b"
    GEMMA3_4B = "gemma3:4b"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_0_FLASH_LITE_001 = "gemini-2.0-flash-lite-001"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GPT_OSS_20B = "gpt-oss:20b"
    
class SettingCreate(BaseModel):
    deny_words: str = ""
    model: ModelEnum = ModelEnum.GEMINI_2_5_FLASH
    temperature: str = "0.2"
    langfuse_enabled: bool = True
    auth_google_enabled: bool = True
    auth_github_enabled: bool = True
    auth_microsoft_enabled: bool = True
    auth_local_enabled: bool = True

class SettingResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    deny_words: str
    model: ModelEnum
    temperature: str
    langfuse_enabled: bool
    auth_google_enabled: bool
    auth_github_enabled: bool
    auth_microsoft_enabled: bool
    auth_local_enabled: bool
    updated_at: datetime
    
class SettingUpdate(BaseModel):
    deny_words: str = None
    model: ModelEnum = None
    temperature: str = None
    langfuse_enabled: bool = None
    auth_google_enabled: bool = None
    auth_github_enabled: bool = None
    auth_microsoft_enabled: bool = None
    auth_local_enabled: bool = None
    
class SettingListResponse(BaseModel):
    settings: List[SettingResponse]