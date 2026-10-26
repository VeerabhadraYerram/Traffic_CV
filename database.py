"""
database.py — Database connection, session management, and retention tooling for UC4 ANPR.
Adheres to Approach 2: isolated tables, no platform schema mutations, automated data retention.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL

# Connection pool optimized for on-premise high-throughput stream processing
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI / Worker dependency for scoped database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes the isolated UC4 database tables safely without mutating platform tables."""
    import models  # Ensure models are imported so Base.metadata knows about them

    with engine.connect() as conn:
        # Ensure UUID extension is available
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        conn.commit()

    # Create only UC4 isolated tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ UC4 database tables verified/initialized.")

def clean_old_records(retention_days: int = None) -> int:
    """
    Data retention job: Purges access logs and related violations older than retention_days.
    Essential for 24/7 on-premise local server stability to prevent unbounded disk growth.
    """
    if retention_days is None:
        retention_days = settings.DATA_RETENTION_DAYS

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    with engine.connect() as conn:
        # Foreign key ondelete="CASCADE" automatically purges corresponding uc4_violations
        result = conn.execute(
            text("DELETE FROM uc4_premise_access_logs WHERE entry_time < :cutoff;"),
            {"cutoff": cutoff_date}
        )
        conn.commit()
        deleted_count = result.rowcount
        logger.info(f"🧹 Retention cleanup: Purged {deleted_count} logs older than {retention_days} days.")
        return deleted_count
