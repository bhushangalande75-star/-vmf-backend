from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from database import get_db
import models, schemas
import httpx
import os
import json

router = APIRouter(prefix="/visitor", tags=["Visitors"])

def _date_filter(q, model, period: str):
    now = datetime.now(timezone.utc)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return q
    return q.filter(model.created_at >= start)

async def get_fcm_access_token() -> str:
    import google.auth.transport.requests
    from google.oauth2 import service_account
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
    if not sa_json:
        print("[FCM] No FIREBASE_SERVICE_ACCOUNT env var!")
        return ""
    try:
        sa_info     = json.loads(sa_json)
        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token or ""
    except Exception as e:
        print(f"[FCM] Token error: {e}")
        return ""

async def send_fcm_notification(token: str, title: str, body: str, data: dict):
    if not token:
        print("[FCM] No token provided")
        return
    try:
        sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
        if not sa_json:
            print("[FCM] No FIREBASE_SERVICE_ACCOUNT env var!")
            return
        sa_info    = json.loads(sa_json)
        project_id = sa_info.get("project_id", "")
        print(f"[FCM] Project ID: {project_id}")
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

        access_token = await get_fcm_access_token()
        if not access_token:
            print("[FCM] Failed to get access token!")
            return

        print(f"[FCM] Got access token, sending notification...")
        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body" : body,
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "sound"               : "visitor_alert",
                        "channel_id"          : "visitor_alerts",
                        "notification_priority": "PRIORITY_MAX",
                        "visibility"          : "PUBLIC",
                        "default_sound"       : False,
                    },
                },
                "data": {k: str(v) for k, v in data.items()},
            }
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json    = payload,
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type" : "application/json",
                },
                timeout = 10,
            )
            print(f"[FCM] Response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"[FCM] Send failed: {e}")

@router.post("/create", response_model=schemas.VisitorResponse, status_code=201)
async def create_visitor(visitor: schemas.VisitorCreate, db: Session = Depends(get_db)):
    if visitor.logged_by is not None:
        guard = db.query(models.User).filter(
            models.User.id == visitor.logged_by).first()
        if not guard:
            raise HTTPException(status_code=404,
                detail=f"Guard with id {visitor.logged_by} not found")
        if guard.role not in ("security", "admin"):
            raise HTTPException(status_code=403,
                detail="Only security personnel can log visitors")

    new_visitor = models.Visitor(
        visitor_name    = visitor.visitor_name,
        phone           = visitor.phone,
        flat_no         = visitor.flat_no,
        visitor_type    = visitor.visitor_type,
        logged_by       = visitor.logged_by,
        checkin_time    = visitor.checkin_time,
        checkin_date    = visitor.checkin_date,
        is_prescheduled = visitor.is_prescheduled,
        society_id      = visitor.society_id,
        status          = "approved" if visitor.is_prescheduled else "pending",
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)

    # Send FCM notification to resident
    if not visitor.is_prescheduled:
        print(f"[FCM] Looking for resident at flat: {new_visitor.flat_no}")
        resident = db.query(models.User).filter(
            models.User.flat_no == new_visitor.flat_no,
            models.User.role    == "member",
            models.User.status  == "active",
        ).first()

        if resident:
            print(f"[FCM] Found resident: {resident.id}, token: {resident.fcm_token}")
        else:
            print(f"[FCM] No resident found for flat: {new_visitor.flat_no}")

        if resident and resident.fcm_token:
            print(f"[FCM] Sending notification...")
            await send_fcm_notification(
                token = resident.fcm_token,
                title = "Visitor at Gate 🔔",
                body  = f"{new_visitor.visitor_name} ({new_visitor.visitor_type}) is at the gate. Approve?",
                data  = {
                    "visitor_id": str(new_visitor.id),
                    "flat_no"   : new_visitor.flat_no,
                    "type"      : "visitor_request",
                },
            )
        elif resident and not resident.fcm_token:
            print(f"[FCM] Resident found but no FCM token!")

    return new_visitor

@router.post("/preschedule", response_model=schemas.VisitorResponse, status_code=201)
def preschedule_visitor(visitor: schemas.VisitorCreate, db: Session = Depends(get_db)):
    new_visitor = models.Visitor(
        visitor_name    = visitor.visitor_name,
        phone           = visitor.phone,
        flat_no         = visitor.flat_no,
        visitor_type    = visitor.visitor_type,
        logged_by       = visitor.logged_by,
        checkin_time    = visitor.checkin_time,
        checkin_date    = visitor.checkin_date,
        is_prescheduled = True,
        society_id      = visitor.society_id,
        status          = "approved",
    )
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)
    return new_visitor

@router.post("/checkout", response_model=schemas.VisitorResponse)
def checkout_visitor(data: schemas.VisitorCheckout, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(
        models.Visitor.id == data.visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.checkout_time:
        raise HTTPException(status_code=409, detail="Visitor already checked out")
    visitor.checkout_time = data.checkout_time
    visitor.checkout_date = data.checkout_date
    db.commit()
    db.refresh(visitor)
    return visitor

@router.post("/approve", response_model=schemas.VisitorResponse)
def approve_visitor(data: schemas.VisitorApprove, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(
        models.Visitor.id == data.visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    if visitor.status != "pending":
        raise HTTPException(status_code=409,
            detail=f"Visitor request is already '{visitor.status}'")
    visitor.status = data.action
    db.commit()
    db.refresh(visitor)
    return visitor

@router.get("/list", response_model=List[schemas.VisitorResponse])
def list_visitors(
    flat_no   : Optional[str] = Query(None),
    status    : Optional[str] = Query(None),
    period    : Optional[str] = Query(None),
    society_id: Optional[int] = Query(None),
    skip      : int           = Query(0, ge=0),
    limit     : int           = Query(20, ge=1, le=100),
    db        : Session       = Depends(get_db),
):
    q = db.query(models.Visitor)
    if flat_no:
        q = q.filter(models.Visitor.flat_no == flat_no)
    if status:
        q = q.filter(models.Visitor.status == status)
    if period:
        q = _date_filter(q, models.Visitor, period)
    if society_id:
        q = q.filter(models.Visitor.society_id == society_id)
    return q.order_by(
        models.Visitor.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/dashboard/metrics")
def dashboard_metrics(
    period    : str           = Query("day"),
    flat_no   : Optional[str] = Query(None),
    society_id: Optional[int] = Query(None),
    db        : Session       = Depends(get_db),
):
    q = db.query(models.Visitor)
    if flat_no:
        q = q.filter(models.Visitor.flat_no == flat_no)
    if society_id:
        q = q.filter(models.Visitor.society_id == society_id)
    q = _date_filter(q, models.Visitor, period)
    all_visitors = q.all()
    return {
        "period"      : period,
        "total"       : len(all_visitors),
        "pending"     : sum(1 for v in all_visitors if v.status == "pending"),
        "approved"    : sum(1 for v in all_visitors if v.status == "approved"),
        "rejected"    : sum(1 for v in all_visitors if v.status == "rejected"),
        "prescheduled": sum(1 for v in all_visitors if v.is_prescheduled),
        "checked_out" : sum(1 for v in all_visitors if v.checkout_time),
    }

@router.get("/{visitor_id}", response_model=schemas.VisitorResponse)
def get_visitor(visitor_id: int, db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(
        models.Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    return visitor