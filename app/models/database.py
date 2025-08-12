from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    scan_tasks = relationship("ScanTask", back_populates="triggered_by_user")

class ScanTask(Base):
    """扫描任务模型"""
    __tablename__ = "scan_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    job_name = Column(String(100), nullable=False)
    jenkins_build_number = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parameters = Column(Text, nullable=True)  # JSON格式的参数
    result = Column(Text, nullable=True)  # JSON格式的结果
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # 关联关系
    triggered_by_user = relationship("User", back_populates="scan_tasks")

class WebSocketConnection(Base):
    """WebSocket连接记录模型"""
    __tablename__ = "websocket_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    
    # 关联关系
    user = relationship("User")