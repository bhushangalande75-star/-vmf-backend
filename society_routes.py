from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db

router = APIRouter(prefix="/society", tags=["Societies"])

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
        "society_id" : society_id,
        "total_users": len(users),
        "members"    : sum(1 for u in users if u.role == "member"),
        "guards"     : sum(1 for u in users if u.role == "security"),
        "admins"     : sum(1 for u in users if u.role == "admin"),
        "pending"    : sum(1 for u in users if u.status == "pending"),
        "visitors_today": len(visitors),
    }

@router.delete("/{society_id}")
def delete_society(society_id: int, db: Session = Depends(get_db)):
    society = db.query(models.Society).filter(
        models.Society.id == society_id).first()
    if not society:
        raise HTTPException(status_code=404, detail="Society not found")
    db.delete(society)
    db.commit()
    return {"message": "Society deleted"}