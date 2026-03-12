from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

def _now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    name         = Column(String,  nullable=False)
    phone        = Column(String,  unique=True, nullable=False, index=True)
    flat_no      = Column(String,  nullable=False)
    role         = Column(String,  nullable=False)  # superadmin/admin/security/member
    password     = Column(String,  nullable=True)   # for admin and guards only
    status       = Column(String,  nullable=False, default="active")  # active/pending/inactive
    society_name = Column(String,  nullable=True)   # which society they belong to
    must_change_password = Column(Boolean, default=False)  # guard first login
    approved_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at   = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    logged_visitors  = relationship("Visitor", back_populates="logged_by_user",
                                    foreign_keys="Visitor.logged_by")

class Visitor(Base):
    __tablename__ = "visitors"

    id            = Column(Integer, primary_key=True, index=True)
    visitor_name  = Column(String,  nullable=False)
    phone         = Column(String,  nullable=False)
    flat_no       = Column(String,  nullable=False, index=True)
    visitor_type  = Column(String,  nullable=False)
    status        = Column(String,  nullable=False, default="pending")  # pending/approved/rejected
    is_prescheduled = Column(Boolean, default=False)  # resident pre-scheduled visit
    checkin_time  = Column(String,  nullable=True)   # manually entered by guard
    checkout_time = Column(String,  nullable=True)   # manually entered by guard
    checkin_date  = Column(String,  nullable=True)   # auto date
    checkout_date = Column(String,  nullable=True)   # auto date
    logged_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by   = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at    = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    logged_by_user  = relationship("User", back_populates="logged_visitors",
                                   foreign_keys=[logged_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        Index("ix_visitors_flat_status", "flat_no", "status"),
    )