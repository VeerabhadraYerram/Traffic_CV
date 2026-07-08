import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# The Docker setup will inject DATABASE_URL, e.g. postgresql://user:password@postgres:5432/traffic
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin@localhost:5432/traffic")

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
