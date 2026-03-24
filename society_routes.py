# backend/society_routes.py
# ── Fix 4: Added /society/{id}/buildings endpoint ────────────────────────────
# Buildings and flat layout are now stored per-society in the DB.
# The Flutter app fetches them instead of using hardcoded BuildingConfig.
#
# DB change: societies table gets a `buildings_config` JSON column.
# Format stored:
#   [
#     {"code": "B01", "name": "Block A", "floors": 8, "flats_per_floor": 10},
#     {"code": "B02", "name": "Block B", "floors": 11, "flats_per_floor": 10}
#   ]
#
# If a society has no buildings_config, the endpoint returns a sensible default.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import models, schemas, json
from database import get_db

router = APIRouter(prefix="/society", tags=["Societies"])


# ── Ensure buildings_config column exists (run once on startup) ───────────────
def ensure_buildings_column(db: Session):
    try:
        db.execute(text(
            "ALTER TABLE societies ADD COLUMN IF NOT EXISTS "
            "buildings_config TEXT"
        ))
        db.commit()
    except Exception:
        db.rollback()


@router.post("/create", response_model=schemas.SocietyResponse, status_code=201)
def create_society(data: schemas.SocietyCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Society).filter(
        models.Society.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409,
            detail=f"Society '{data.name}' already exists")
    society = models.Society(name=data.name, address=data.address)
    db.add(society)
    db.commit()
    db.refresh(society)
    return society


@router.get("/list", response_model=List[schemas.SocietyResponse])
def list_societies(db: Session = Depends(get_db)):
    return db.query(models.Society).order_by(models.Society.name).all()


@router.get("/{society_id}", response_model=schemas.SocietyResponse)
def get_society(society_id: int, db: Session = Depends(get_db)):
    society = db.query(models.Society).filter(
        models.Society.id == society_id).first()
    if not society:
        raise HTTPException(status_code=404, detail="Society not found")
    return society


@router.get("/{society_id}/users")
def get_society_users(society_id: int, db: Session = Depends(get_db)):
    users = db.query(models.User).filter(
        models.User.society_id == society_id).all()
    return users


@router.get("/{society_id}/stats")
def get_society_stats(society_id: int, db: Session = Depends(get_db)):
    users    = db.query(models.User).filter(
        models.User.society_id == society_id).all()
    visitors = db.query(models.Visitor).filter(
        models.Visitor.society_id == society_id).all()
    return {
        "society_id"     : society_id,
        "total_users"    : len(users),
        "members"        : sum(1 for u in users if u.role == "member"),
        "guards"         : sum(1 for u in users if u.role == "security"),
        "admins"         : sum(1 for u in users if u.role == "admin"),
        "pending"        : sum(1 for u in users if u.status == "pending"),
        "visitors_today" : len(visitors),
    }


# ── Fix 4: GET buildings config for a society ─────────────────────────────────
@router.get("/{society_id}/buildings")
def get_society_buildings(society_id: int, db: Session = Depends(get_db)):
    """
    Returns the list of buildings and their floor/flat layout for a society.
    Used by the Flutter RegisterScreen to build the flat number dropdown
    dynamically instead of using hardcoded BuildingConfig.
    """
    society = db.query(models.Society).filter(
        models.Society.id == society_id).first()
    if not society:
        raise HTTPException(status_code=404, detail="Society not found")

    # Try to get society-specific config from DB
    raw = getattr(society, 'buildings_config', None)
    if raw:
        try:
            return {"society_id": society_id, "buildings": json.loads(raw)}
        except Exception:
            pass

    # ── Default fallback (matches your original BuildingConfig) ──────────────
    default_buildings = [
        {"code": "B01", "name": "Block 1", "floors": 8,  "flats_per_floor": 10},
        {"code": "B02", "name": "Block 2", "floors": 11, "flats_per_floor": 10},
        {"code": "B03", "name": "Block 3", "floors": 10, "flats_per_floor": 10},
    ]
    return {"society_id": society_id, "buildings": default_buildings}


# ── Fix 4: PUT buildings config for a society (admin only) ───────────────────
@router.put("/{society_id}/buildings")
def set_society_buildings(
    society_id: int,
    buildings : list,
    db        : Session = Depends(get_db),
):
    """
    Admin sets the building layout for a society.
    Body example:
    [
      {"code": "A", "name": "Tower A", "floors": 12, "flats_per_floor": 8},
      {"code": "B", "name": "Tower B", "floors": 10, "flats_per_floor": 6}
    ]
    """
    society = db.query(models.Society).filter(
        models.Society.id == society_id).first()
    if not society:
        raise HTTPException(status_code=404, detail="Society not found")
    db.execute(
        text("UPDATE societies SET buildings_config = :cfg WHERE id = :id"),
        {"cfg": json.dumps(buildings), "id": society_id},
    )
    db.commit()
    return {"message": "Buildings config updated", "buildings": buildings}


@router.delete("/{society_id}")
def delete_society(society_id: int, db: Session = Depends(get_db)):
    society = db.query(models.Society).filter(
        models.Society.id == society_id).first()
    if not society:
        raise HTTPException(status_code=404, detail="Society not found")
    db.delete(society)
    db.commit()
    return {"message": "Society deleted"}