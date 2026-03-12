from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import datetime
import re


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_phone(v: str) -> str:
    # FIX: validate phone is digits only, 7–15 chars (E.164-style)
    if not re.fullmatch(r"\d{7,15}", v):
        raise ValueError("Phone must be 7–15 digits with no spaces or symbols")
    return v


# ── User Schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name    : str
    phone   : str
    flat_no : str
    # FIX: restrict role to known values instead of accepting any string
    role    : Literal["admin", "security", "member"]

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be blank")
        return v.strip()


class UserLogin(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)


# Response model — never expose internal columns you don't intend to share
class UserResponse(BaseModel):
    id         : int
    name       : str
    phone      : str
    flat_no    : str
    role       : str
    created_at : datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    message  : str
    user_id  : int
    role     : str
    flat_no  : str


# ── Visitor Schemas ───────────────────────────────────────────────────────────

class VisitorCreate(BaseModel):
    visitor_name : str
    phone        : str
    flat_no      : str
    visitor_type : str
    logged_by    : Optional[int] = None   # security guard user ID

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

    @field_validator("visitor_name", "flat_no", "visitor_type")
    @classmethod
    def not_empty(cls, v):
        if not v.strip():
            raise ValueError("Field cannot be blank")
        return v.strip()


class VisitorApprove(BaseModel):
    visitor_id : int
    # FIX: only allow these two values — previously any string was accepted
    action     : Literal["approved", "rejected"]


class VisitorResponse(BaseModel):
    id           : int
    visitor_name : str
    phone        : str
    flat_no      : str
    visitor_type : str
    status       : str
    logged_by    : Optional[int]
    created_at   : datetime
    updated_at   : datetime

    model_config = {"from_attributes": True}
