from pydantic import BaseModel
from typing import Optional

class RoleCreate(BaseModel):
    name: str

class RoleResponse(BaseModel):
    id: str
    name: str

class RoleUpdate(BaseModel):
    name: Optional[str] = None
