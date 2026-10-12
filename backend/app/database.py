from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Ensure sqlite DB path resolves consistently to backend/trade_intelligence.db
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///./") or db_url == "sqlite:///trade_intelligence.db":
    backend_dir = Path(__file__).resolve().parent.parent
    db_file = backend_dir / "trade_intelligence.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

connect_args = {}
if "sqlite" in db_url:
    connect_args = {
        "check_same_thread": False,
        "timeout": 30
    }

engine = create_engine(
    db_url,
    connect_args=connect_args
)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

