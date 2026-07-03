from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

# PostgreSQL + pgvector
DATABASE_URL = (
    "postgresql+psycopg://postgres:password@localhost:5432/duui"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

Session = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_database():
    """
    Erstellt alle Tabellen.
    """
    Base.metadata.create_all(engine)


def get_session():
    """
    Liefert eine neue SQLAlchemy-Session.
    """
    return Session()