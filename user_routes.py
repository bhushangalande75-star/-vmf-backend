from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas
from database import get_db
import hashlib

router = APIRouter(prefix="/user", tags=["Users"])

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ── Register (Member self-registration → status=pending) ─────────────────────

@router.post("/create", response_model=schemas.UserResponse, status_code=201)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == user.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Phone {user.phone} already registered")

    # Members start as pending until admin approves
    user_status = "pending" if user.role == "member" else "active"

    new_user = models.User(
        name         = user.name,
        phone        = user.phone,
        flat_no      = user.flat_no,
        role         = user.role,
        status       = user_status,
        society_name = user.society_name,
        password     = _hash(user.password) if user.password else None,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ── Admin creates Guard account ───────────────────────────────────────────────

@router.post("/create-guard", response_model=schemas.UserResponse, status_code=201)
def create_guard(data: schemas.GuardCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Phone {data.phone} already registered")

    guard = models.User(
        name                 = data.name,
        phone                = data.phone,
        flat_no              = data.flat_no,
        role                 = "security",
        status               = "active",
        society_name         = data.society_name,
        password             = _hash(data.password),
        must_change_password = True,
    )
    db.add(guard)
    db.commit()
    db.refresh(guard)
    return guard


# ── Login (OTP for members, password for admin/guard) ────────────────────────

@router.post("/login", response_model=schemas.LoginResponse)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.phone == user.phone).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Admin and guard require password
    if db_user.role in ("admin", "security", "superadmin"):
        if not user.password:
            raise HTTPException(status_code=400, detail="Password required")
        if db_user.password != _hash(user.password):
            raise HTTPException(status_code=401, detail="Invalid password")

    # Pending members cannot login
    if db_user.status == "pending":
        raise HTTPException(status_code=403,
            detail="Account pending approval by admin")

    if db_user.status == "inactive":
        raise HTTPException(status_code=403, detail="Account is inactive")

    return {
        "message"              : "Login successful",
        "user_id"              : db_user.id,
        "role"                 : db_user.role,
        "flat_no"              : db_user.flat_no,
        "status"               : db_user.status,
        "must_change_password" : db_user.must_change_password or False,
    }


# ── Admin approves/rejects resident registration ──────────────────────────────

@router.post("/approve")
def approve_user(data: schemas.UserApprove, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != "pending":
        raise HTTPException(status_code=409, detail="User is not pending approval")

    user.status = "active" if data.action == "approved" else "inactive"
    db.commit()
    return {"message": f"User {data.action} successfully"}


# ── Change password (guard first login) ───────────────────────────────────────

@router.post("/change-password")
def change_password(data: schemas.PasswordChange, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password             = _hash(data.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}


# ── Get all pending registrations (admin) ─────────────────────────────────────

@router.get("/pending/list")
def pending_users(db: Session = Depends(get_db)):
    users = db.query(models.User).filter(models.User.status == "pending").all()
    return users


# ── Get all users (admin dashboard) ──────────────────────────────────────────

@router.get("/list/all")
def list_users(
    role        : Optional[str] = None,
    society_name: Optional[str] = None,
    db          : Session = Depends(get_db)
):
    q = db.query(models.User)
    if role:
        q = q.filter(models.User.role == role)
    if society_name:
        q = q.filter(models.User.society_name == society_name)
    return q.all()


# ── Delete user ───────────────────────────────────────────────────────────────

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


# ── Get single user ───────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user