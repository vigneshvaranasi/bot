import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ...db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, unique=True, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    users = relationship("User", back_populates="role")
