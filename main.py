from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import models
from database import engine
from visitor_routes  import router as visitor_router
from user_routes     import router as user_router
from society_routes  import router as society_router

def run_migrations():
    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS society_name VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS society_id INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    run_migrations()
    yield

app = FastAPI(
    title    = "Visitor Management System",
    version  = "3.0.0",
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
    return {"message": "VMF Backend Running", "version": "3.0.0"}