from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine
from visitor_routes import router as visitor_router
from user_routes import router as user_router


# FIX: use lifespan for startup logic (the old @app.on_event is deprecated)
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title       = "Visitor Management System",
    description = "Backend API for security gate visitor management",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# FIX: CORS was completely missing — needed for web / mobile frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # ← restrict to your domain in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(visitor_router)
app.include_router(user_router)


@app.get("/", tags=["Health"])
def home():
    return {"message": "VMF Backend Running", "version": "1.0.0"}
