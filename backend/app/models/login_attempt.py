from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, Index
from app.models.base import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False)
    email = Column(String(255), nullable=False)
    attempt_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_success = Column(Boolean, nullable=False)

    __table_args__ = (
        Index("idx_login_attempts_lookup", "ip_address", "attempt_time"),
        Index("idx_login_attempts_email", "email", "attempt_time"),
    )
