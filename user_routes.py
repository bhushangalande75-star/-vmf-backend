from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone, timedelta
import models, schemas
from database import get_db
import hashlib, secrets, os
import httpx


router = APIRouter(prefix="/user", tags=["Users"])

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _send_email(to_email: str, subject: str, body: str):
    api_key    = os.getenv("BREVO_API_KEY", "")
    smtp_email = os.getenv("SMTP_EMAIL", "societyvmf@gmail.com")
    if not api_key:
        print(f"[EMAIL] Brevo not configured.")
        return
    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key"     : api_key,
                "Content-Type": "application/json",
            },
            json={
                "sender"     : {"name": "VMF Society", "email": smtp_email},
                "to"         : [{"email": to_email}],
                "subject"    : subject,
                "htmlContent": body,
            },
            timeout=10,
        )
        if response.status_code == 201:
            print(f"[EMAIL] Sent to {to_email}")
        else:
            print(f"[EMAIL] Brevo error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[EMAIL] Failed: {e}")

# ── Register (all roles) ──────────────────────────────────────────────────────

@router.post("/create", response_model=schemas.UserResponse, status_code=201)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        models.User.phone == user.phone).first()
    if existing:
        raise HTTPException(status_code=409,
            detail=f"Phone {user.phone} already registered")

    if not user.password:
        raise HTTPException(status_code=400,
            detail="Password is required for registration")

    user_status = "pending" if user.role == "member" else "active"
    new_user = models.User(
        name         = user.name,
        phone        = user.phone,
        email        = user.email,
        flat_no      = user.flat_no,
        role         = user.role,
        status       = user_status,
        society_name = user.society_name,
        society_id   = user.society_id,
        password     = _hash(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ── Admin creates Guard or Admin account ──────────────────────────────────────

@router.post("/create-guard", response_model=schemas.UserResponse, status_code=201)
def create_guard(data: schemas.GuardCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        models.User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=409,
            detail=f"Phone {data.phone} already registered")
    guard = models.User(
        name                 = data.name,
        phone                = data.phone,
        email                = data.email,
        flat_no              = data.flat_no,
        role                 = data.role,
        status               = "active",
        society_name         = data.society_name,
        society_id           = data.society_id,
        password             = _hash(data.password),
        must_change_password = True if data.role == "security" else False,
    )
    db.add(guard)
    db.commit()
    db.refresh(guard)
    return guard

# ── Login (ALL roles use phone + password now) ────────────────────────────────

@router.post("/login", response_model=schemas.LoginResponse)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        models.User.phone == user.phone).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.password != _hash(user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

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
        "society_id"           : db_user.society_id,
        "society_name"         : db_user.society_name,
        "must_change_password" : db_user.must_change_password or False,
    }

# ── Forgot Password — sends code to email ─────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(data: schemas.ForgotPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == data.email).first()
    if not user:
        # Don't reveal if email exists or not (security)
        return {"message": "If this email is registered, a reset code has been sent."}

    # Generate 6-digit reset code
    reset_code   = str(secrets.randbelow(900000) + 100000)
    expiry       = datetime.now(timezone.utc) + timedelta(minutes=15)

    user.reset_token        = _hash(reset_code)
    user.reset_token_expiry = expiry
    db.commit()

    # Send email
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                background:#f9f9f9;border-radius:12px;">
      <h2 style="color:#1A6B3A">VMF — Password Reset</h2>
      <p>Hello <b>{user.name}</b>,</p>
      <p>Your password reset code is:</p>
      <div style="font-size:36px;font-weight:bold;letter-spacing:8px;
                  color:#1A6B3A;padding:20px;background:#E8F5EC;
                  border-radius:8px;text-align:center;margin:20px 0">
        {reset_code}
      </div>
      <p>This code expires in <b>15 minutes</b>.</p>
      <p>If you did not request this, please ignore this email.</p>
      <hr style="border:none;border-top:1px solid #ddd;margin:24px 0"/>
      <p style="color:#999;font-size:12px">VMF — Visitor Management Framework</p>
    </div>
    """
    _send_email(data.email, "VMF — Password Reset Code", body)
    return {"message": "If this email is registered, a reset code has been sent."}

# ── Reset Password with code ───────────────────────────────────────────────────

@router.post("/reset-password")
def reset_password(data: schemas.ResetPassword, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.email == data.email).first()
    if not user or not user.reset_token or not user.reset_token_expiry:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")

    # Check expiry
    if datetime.now(timezone.utc) > user.reset_token_expiry:
        raise HTTPException(status_code=400, detail="Reset code has expired")

    # Verify code
    if user.reset_token != _hash(data.reset_code):
        raise HTTPException(status_code=400, detail="Invalid reset code")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400,
            detail="Password must be at least 6 characters")

    user.password             = _hash(data.new_password)
    user.reset_token          = None
    user.reset_token_expiry   = None
    user.must_change_password = False
    db.commit()
    return {"message": "Password reset successfully. Please login with your new password."}

# ── Change password (guard first login) ───────────────────────────────────────

@router.post("/change-password")
def change_password(data: schemas.PasswordChange, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password             = _hash(data.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password changed successfully"}

# ── Admin approves/rejects member ────────────────────────────────────────────

@router.post("/approve")
def approve_user(data: schemas.UserApprove, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != "pending":
        raise HTTPException(status_code=409, detail="User is not pending approval")
    user.status = "active" if data.action == "approved" else "inactive"
    db.commit()

    # Send approval email if email exists
    if user.email and data.action == "approved":
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                    background:#f9f9f9;border-radius:12px;">
          <h2 style="color:#1A6B3A">✅ Account Approved!</h2>
          <p>Hello <b>{user.name}</b>,</p>
          <p>Your VMF account has been approved by the admin.</p>
          <p>You can now login using your phone number and password.</p>
          <p><b>Phone (Username):</b> {user.phone}</p>
          <hr style="border:none;border-top:1px solid #ddd;margin:24px 0"/>
          <p style="color:#999;font-size:12px">VMF — Visitor Management Framework</p>
        </div>
        """
        _send_email(user.email, "VMF — Account Approved!", body)

    return {"message": f"User {data.action} successfully"}

# ── Update FCM token ──────────────────────────────────────────────────────────

@router.post("/update-token")
def update_fcm_token(
    user_id  : int = Query(...),
    fcm_token: str = Query(...),
    db       : Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.fcm_token = fcm_token
    db.commit()
    return {"message": "Token updated"}

# ── Pending list ──────────────────────────────────────────────────────────────

@router.get("/pending/list")
def pending_users(
    society_id: Optional[int] = None,
    db        : Session = Depends(get_db)
):
    q = db.query(models.User).filter(models.User.status == "pending")
    if society_id:
        q = q.filter(models.User.society_id == society_id)
    return q.all()

# ── List all users ────────────────────────────────────────────────────────────

@router.get("/list/all")
def list_users(
    role        : Optional[str] = None,
    society_id  : Optional[int] = None,
    society_name: Optional[str] = None,
    db          : Session = Depends(get_db)
):
    q = db.query(models.User)
    if role:         q = q.filter(models.User.role == role)
    if society_id:   q = q.filter(models.User.society_id == society_id)
    if society_name: q = q.filter(models.User.society_name == society_name)
    return q.all()

# ── Delete user ───────────────────────────────────────────────────────────────

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

# ── Update profile ────────────────────────────────────────────────────────────

@router.post("/update-profile")
def update_profile(
    user_id     : int            = Query(...),
    name        : Optional[str]  = Query(None),
    email       : Optional[str]  = Query(None),
    phone       : Optional[str]  = Query(None),
    db          : Session        = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if name  is not None: user.name  = name
    if email is not None: user.email = email
    if phone is not None:
        # Check phone not taken by another user
        existing = db.query(models.User).filter(
            models.User.phone == phone,
            models.User.id    != user_id).first()
        if existing:
            raise HTTPException(status_code=409,
                detail="Phone number already registered to another account")
        user.phone = phone

    db.commit()
    db.refresh(user)
    return {"message": "Profile updated successfully",
            "user"   : {
                "id"    : user.id,
                "name"  : user.name,
                "email" : user.email,
                "phone" : user.phone,
            }}

# ── Update password from profile ──────────────────────────────────────────────

@router.post("/update-password")
def update_password(
    user_id     : int = Query(...),
    old_password: str = Query(...),
    new_password: str = Query(...),
    db          : Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password != _hash(old_password):
        raise HTTPException(status_code=401,
            detail="Current password is incorrect")
    if len(new_password) < 6:
        raise HTTPException(status_code=400,
            detail="New password must be at least 6 characters")
    user.password             = _hash(new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Password updated successfully"}
    
# ── Get single user ───────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user