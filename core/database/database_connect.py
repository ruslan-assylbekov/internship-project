from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models.database_models import Base
import os

db_path = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:a2bf9c79@localhost:5432/internship-project"
)

# For Docker: "postgresql://user:password@db:5432/mydb"

engine = create_engine(db_path)
Session = sessionmaker(bind=engine)

def init_db():
    """Creates all tables if they don't exist."""
    Base.metadata.create_all(engine)

def get_session():
    return Session()