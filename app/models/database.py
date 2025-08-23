from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scan_tasks = relationship("ScanTask", back_populates="triggered_by_user")

class ScanTask(Base):
    """Scan task model"""
    __tablename__ = "scan_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    job_name = Column(String(100), nullable=False)
    jenkins_build_number = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parameters = Column(Text, nullable=True)  # JSON format parameters
    result = Column(Text, nullable=True)  # JSON format result
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    triggered_by_user = relationship("User", back_populates="scan_tasks")

class WebSocketConnection(Base):
    """WebSocket connection record model"""
    __tablename__ = "websocket_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User")

class MonitorTask(Base):
    """Third-party service monitoring task model"""
    __tablename__ = "monitor_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    service_name = Column(String(100), nullable=False)  # Third-party service name
    job_id = Column(String(100), nullable=False)  # Third-party service job ID
    monitor_url = Column(String(500), nullable=False)  # GET request URL for monitoring
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed, timeout
    result = Column(Text, nullable=True)  # JSON format final result
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    timeout_at = Column(DateTime, nullable=False)  # Timeout time after 30 minutes
    
    # Monitoring configuration
    check_interval = Column(Integer, default=30)  # Check interval in seconds
    success_conditions = Column(Text, nullable=True)  # JSON format success conditions
    failure_conditions = Column(Text, nullable=True)  # JSON format failure conditions
    
    # Multi-instance support fields
    assigned_instance = Column(String(100), nullable=True, index=True)  # Instance ID handling this task
    last_heartbeat = Column(DateTime, nullable=True, index=True)  # Last heartbeat timestamp
    retry_count = Column(Integer, default=0)  # Number of retries
    max_retries = Column(Integer, default=3)  # Maximum retry attempts