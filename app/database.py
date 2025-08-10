import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)

# 数据库连接URL - 支持SQLite和Oracle
DATABASE_URL = os.getenv("DATABASE_URL", f"oracle+oracledb://{settings.ORACLE_USER}:{settings.ORACLE_PASSWORD}@{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/{settings.ORACLE_SERVICE}")

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=settings.DEBUG,  # 在调试模式下显示SQL语句
    pool_pre_ping=True,   # 连接池预检查
    pool_recycle=3600     # 连接回收时间（秒）
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基础模型类
Base = declarative_base()

def get_db() -> Session:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

def create_tables():
    """创建数据库表"""
    try:
        from app.models.database import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise