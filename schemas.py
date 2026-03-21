from pydantic import BaseModel, field_validator, EmailStr
from typing import Literal, Optional
from datetime import datetime
import re

def _validate_phone(v: str) -> str:
    if not re.fullmatch(r"\d{7,15}", v):
        raise ValueError("Phone must be 7-15 digits")
    return v

# ── Society ───────────────────────────────────────────────────────────────────

class SocietyCreate(BaseModel):
    name    : str
    address : str

class SocietyResponse(BaseModel):
    id        : int
    name      : str
    address   : str
    is_active : bool
    created_at: datetime
    model_config = {"from_attributes": True}

# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name         : str
    phone        : str
    email        : Optional[str] = None
    flat_no      : str
    role         : Literal["superadmin", "admin", "security", "member"]
    password     : Optional[str] = None
    society_name : Optional[str] = None
    society_id   : Optional[int] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip(): raise ValueError("Name cannot be blank")
        return v.strip()

class UserLogin(BaseModel):
    phone    : str
    password : str

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

class GuardCreate(BaseModel):
    name         : str
    phone        : str
    email        : Optional[str] = None
    flat_no      : str = "GATE"
    password     : str
    role         : Literal["security", "admin"] = "security"
    society_name : Optional[str] = None
    society_id   : Optional[int] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

class UserApprove(BaseModel):
    user_id : int
    action  : Literal["approved", "rejected"]

class PasswordChange(BaseModel):
    user_id      : int
    new_password : str

class ForgotPassword(BaseModel):
    email : str

class ResetPassword(BaseModel):
    email        : str
    reset_code   : str
    new_password : str

class UserResponse(BaseModel):
    id           : int
    name         : str
    phone        : str
    email        : Optional[str]
    flat_no      : str
    role         : str
    status       : str
    society_name : Optional[str]
    society_id   : Optional[int]
    created_at   : datetime
    model_config = {"from_attributes": True}

class LoginResponse(BaseModel):
    message              : str
    user_id              : int
    role                 : str
    flat_no              : str
    status               : str
    society_id           : Optional[int] = None
    society_name         : Optional[str] = None
    must_change_password : bool = False

# ── Visitor ───────────────────────────────────────────────────────────────────

class VisitorCreate(BaseModel):
    visitor_name    : str
    phone           : str
    flat_no         : str
    visitor_type    : str
    logged_by       : Optional[int] = None
    checkin_time    : Optional[str] = None
    checkin_date    : Optional[str] = None
    is_prescheduled : bool = False
    society_id      : Optional[int] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v): return _validate_phone(v)

    @field_validator("visitor_name", "flat_no", "visitor_type")
    @classmethod
    def not_empty(cls, v):
        if not v.strip(): raise ValueError("Field cannot be blank")
        return v.strip()

class VisitorCheckout(BaseModel):
    visitor_id    : int
    checkout_time : str
    checkout_date : str

class VisitorApprove(BaseModel):
    visitor_id : int
    action     : Literal["approved", "rejected"]

class VisitorResponse(BaseModel):
    id              : int
    visitor_name    : str
    phone           : str
    flat_no         : str
    visitor_type    : str
    status          : str
    is_prescheduled : bool
    checkin_time    : Optional[str]
    checkout_time   : Optional[str]
    checkin_date    : Optional[str]
    checkout_date   : Optional[str]
    logged_by       : Optional[int]
    society_id      : Optional[int]
    created_at      : datetime
    updated_at      : datetime
    model_config = {"from_attributes": True}