"""
Database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.core.config import config
from backend.core.logger import logger
from backend.database.models import Base
import os


class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database connection"""
        try:
            # Get database URL from config
            db_url = config.get("database.url")

            if not db_url:
                # Use ConfigManager settings with proper defaults
                db_user = os.getenv("DB_USER") or config.settings.db_user
                db_pass = os.getenv("DB_PASSWORD") or config.settings.db_password
                db_host = os.getenv("DB_HOST") or config.settings.db_host
                db_port = os.getenv("DB_PORT") or config.settings.db_port
                db_name = os.getenv("DB_NAME") or config.settings.db_name

                db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
                logger.info(
                    "Connecting to database: %s@%s:%s/%s",
                    db_user,
                    db_host,
                    db_port,
                    db_name,
                )
            else:
                logger.info("Connecting to database using URL from configuration")

            # Create engine
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,  # Test connections before using
                echo=False  # Set to True for SQL debugging
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info(f"✓ Database connected: {db_host}:{db_port}/{db_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            # Don't crash - allow system to run without DB
            self.engine = None
            self.SessionLocal = None
    
    def create_tables(self):
        """Create all tables"""
        if self.engine:
            try:
                Base.metadata.create_all(bind=self.engine)
                logger.info("✓ Database tables created/verified")
            except Exception as e:
                logger.error(f"Failed to create tables: {e}")
    
    def get_session(self) -> Session:
        """Get database session"""
        if self.SessionLocal:
            return self.SessionLocal()
        return None
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


# Global database instance
db = Database()


def get_db():
    """Dependency for FastAPI routes"""
    session = db.get_session()
    if session:
        try:
            yield session
        finally:
            session.close()
    else:
        yield None
