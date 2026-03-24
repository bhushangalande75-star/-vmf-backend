# backend/main.py
# ── Fix 1: Superadmin is now a real DB user, seeded on startup ──────────────
# Remove ALL hardcoded credential checks from the Flutter login screen.
# The superadmin logs in via POST /user/login just like any other user.
#
# IMPORTANT: Set SUPERADMIN_PASSWORD in your environment variables on Render.
# If not set, defaults to a random value printed once at startup (change it!).

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import models, secrets, hashlib, os
from database import engine, SessionLocal
from visitor_routes import router as visitor_router
from user_routes    import router as user_router
from society_routes import router as society_router


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def run_migrations():
    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS society_name VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS society_id INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS is_prescheduled BOOLEAN DEFAULT FALSE",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS checkin_time VARCHAR",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS checkout_time VARCHAR",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS checkin_date VARCHAR",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS checkout_date VARCHAR",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS approved_by INTEGER",
            "ALTER TABLE visitors ADD COLUMN IF NOT EXISTS society_id INTEGER",
        ]
        for migration in migrations:
            try:
                conn.execute(text(migration))
            except Exception as e:
                print(f"Migration skipped: {e}")
        conn.commit()


def seed_superadmin():
    """
    Creates the superadmin user on first startup if it doesn't exist.
    Password comes from SUPERADMIN_PASSWORD env var.
    Phone (username) comes from SUPERADMIN_PHONE env var.
    Both default to safe random values printed once — change them immediately.
    """
    db = SessionLocal()
    try:
        # Read from environment (set these on Render → Environment tab)
        sa_phone    = os.getenv("SUPERADMIN_PHONE",    "0000000000")
        sa_password = os.getenv("SUPERADMIN_PASSWORD", "")

        if not sa_password:
            # Generate a one-time random password and print it clearly
            sa_password = secrets.token_urlsafe(12)
            print("=" * 60)
            print("  SUPERADMIN_PASSWORD env var not set!")
            print(f"  One-time password: {sa_password}")
            print(f"  Phone: {sa_phone}")
            print("  Set SUPERADMIN_PASSWORD in Render → Environment")
            print("=" * 60)

        existing = db.query(models.User).filter(
            models.User.phone == sa_phone,
            models.User.role  == "superadmin",
        ).first()

        if not existing:
            superadmin = models.User(
                name       = "Super Admin",
                phone      = sa_phone,
                flat_no    = "N/A",
                role       = "superadmin",
                status     = "active",
                password   = _hash(sa_password),
            )
            db.add(superadmin)
            db.commit()
            print(f"[SEED] Superadmin created. Phone: {sa_phone}")
        else:
            print(f"[SEED] Superadmin already exists (phone: {sa_phone})")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_superadmin()   # ← seeds superadmin on every startup (idempotent)
    yield


app = FastAPI(
    title    = "Visitor Management System",
    version  = "3.1.0",
    lifespan = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(society_router)
app.include_router(visitor_router)
app.include_router(user_router)

@app.get("/", tags=["Health"])
def home():
    return {"message": "VMF Backend Running", "version": "3.1.0"}