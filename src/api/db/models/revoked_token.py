from sqlalchemy import Column, String, DateTime
from ...db.base import Base

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String, primary_key=True)
    expires_at = Column(DateTime, nullable=False)
