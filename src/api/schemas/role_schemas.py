from pydantic import BaseModel

class RoleResponse(BaseModel):
    id: str
    name: str