from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./vmf.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# FIX: declarative_base() is deprecated in SQLAlchemy 2.x
class Base(DeclarativeBase):
    pass


# FIX: Centralised get_db — import this in routes instead of redefining it
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
