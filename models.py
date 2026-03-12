from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String,  nullable=False)
    phone      = Column(String,  unique=True, nullable=False, index=True)
    flat_no    = Column(String,  nullable=False)
    # FIX: role accepts only: admin / security / member (enforced in schema)
    role       = Column(String,  nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # Visitors logged by this guard
    logged_visitors = relationship("Visitor", back_populates="logged_by_user")


class Visitor(Base):
    __tablename__ = "visitors"

    id           = Column(Integer, primary_key=True, index=True)
    visitor_name = Column(String,  nullable=False)
    phone        = Column(String,  nullable=False)
    flat_no      = Column(String,  nullable=False, index=True)
    visitor_type = Column(String,  nullable=False)
    # FIX: status accepts only: pending / approved / rejected (enforced in schema)
    status       = Column(String,  nullable=False, default="pending")
    # FIX: track which security guard created the entry
    logged_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now,  nullable=False)
    updated_at   = Column(DateTime(timezone=True), default=_now,  onupdate=_now, nullable=False)

    logged_by_user = relationship("User", back_populates="logged_visitors")

    # Index for the most common query: visitors for a flat filtered by status
    __table_args__ = (
        Index("ix_visitors_flat_status", "flat_no", "status"),
    )
