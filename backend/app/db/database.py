# app/db/database.py
# Sets up the SQLAlchemy engine and session factory.
# SQLAlchemy is an ORM — it lets you work with your PostgreSQL database
# using Python objects instead of raw SQL queries.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# The engine is the actual connection to your PostgreSQL database
engine = create_engine(settings.DATABASE_URL)

# SessionLocal is a factory — call it to get a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class all your database models will inherit from
Base = declarative_base()


def get_db():
    """
    FastAPI dependency: opens a DB session for each request,
    then automatically closes it when the request finishes.
    
    Usage in route:  db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()