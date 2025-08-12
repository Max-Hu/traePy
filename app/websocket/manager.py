from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import json
import asyncio
from datetime import datetime

from app.models.database import User, WebSocketConnection, ScanTask
from app.auth.jwt_auth import verify_token
from app.database import SessionLocal
from app.logger import setup_logger

logger = setup_logger(__name__)

class ConnectionManager:
    """WebSocket connection manager"""
    
    def __init__(self):
        # 存储活跃连接: {user_id: {connection_id: websocket}}
        self.active_connections: Dict[int, Dict[str, WebSocket]] = {}
        # 存储用户连接映射: {connection_id: user_id}
        self.connection_user_map: Dict[str, int] = {}
    
    async def connect(self, websocket: WebSocket, user: User, connection_id: str, db: Session = None):
        """建立WebSocket连接"""
        await websocket.accept()
        
        # 初始化用户连接字典
        if user.id not in self.active_connections:
            self.active_connections[user.id] = {}
        
        # 添加连接
        self.active_connections[user.id][connection_id] = websocket
        self.connection_user_map[connection_id] = user.id
        
        # 记录到数据库
        if db is None:
            db = SessionLocal()
            should_close_db = True
        else:
            should_close_db = False
            
        try:
            db_connection = WebSocketConnection(
                connection_id=connection_id,
                user_id=user.id,
                is_active=True
            )
            db.add(db_connection)
            db.commit()
            logger.info(f"WebSocket connected: user={user.username}, connection_id={connection_id}")
        except Exception as e:
            logger.error(f"Failed to record WebSocket connection: {str(e)}")
        finally:
            if should_close_db:
                db.close()
    
    def disconnect(self, connection_id: str, db: Session = None):
        """断开WebSocket连接"""
        if connection_id in self.connection_user_map:
            user_id = self.connection_user_map[connection_id]
            
            # 从活跃连接中移除
            if user_id in self.active_connections and connection_id in self.active_connections[user_id]:
                del self.active_connections[user_id][connection_id]
                
                # 如果用户没有其他连接，移除用户记录
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # 从连接映射中移除
            del self.connection_user_map[connection_id]
            
            # 更新数据库记录
            if db is None:
                db = SessionLocal()
                should_close_db = True
            else:
                should_close_db = False
            try:
                db_connection = db.query(WebSocketConnection).filter(
                    WebSocketConnection.connection_id == connection_id
                ).first()
                if db_connection:
                    db_connection.is_active = False
                    db_connection.disconnected_at = datetime.utcnow()
                    db.commit()
                logger.info(f"WebSocket disconnected: connection_id={connection_id}")
            except Exception as e:
                logger.error(f"Failed to update WebSocket disconnection: {str(e)}")
            finally:
                if should_close_db:
                    db.close()
    
    async def send_personal_message(self, message: dict, user_id: int):
        """向特定用户发送消息"""
        if user_id in self.active_connections:
            disconnected_connections = []
            
            for connection_id, websocket in self.active_connections[user_id].items():
                try:
                    await websocket.send_text(json.dumps(message))
                    logger.debug(f"Message sent to user {user_id}, connection {connection_id}")
                except Exception as e:
                    logger.error(f"Failed to send message to connection {connection_id}: {str(e)}")
                    disconnected_connections.append(connection_id)
            
            # 清理断开的连接
            for connection_id in disconnected_connections:
                self.disconnect(connection_id)
    
    async def send_task_update(self, task: ScanTask):
        """向任务触发者发送任务状态更新"""
        message = {
            "type": "task_update",
            "data": {
                "task_id": task.task_id,
                "job_name": task.job_name,
                "status": task.status,
                "jenkins_build_number": task.jenkins_build_number,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "result": json.loads(task.result) if task.result else None
            }
        }
        
        await self.send_personal_message(message, task.triggered_by)
        logger.info(f"Task update sent: task_id={task.task_id}, user_id={task.triggered_by}")
    
    async def handle_client_message(self, websocket: WebSocket, connection_id: str, message: dict, db: Session = None):
        """处理客户端消息"""
        user_id = self.connection_user_map.get(connection_id)
        if not user_id:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Invalid connection"
            }))
            return
        
        message_type = message.get("type")
        logger.info(f"Received message from user {user_id}: type={message_type}")
        
        if message_type == "ping":
            # 心跳检测
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            }))
        
        elif message_type == "get_tasks":
            # 获取用户的任务列表
            await self._send_user_tasks(websocket, user_id, db)
        
        elif message_type == "cancel_task":
            # 取消任务（如果支持的话）
            task_id = message.get("task_id")
            if task_id:
                await self._cancel_task(websocket, user_id, task_id)
        
        else:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }))
    
    async def _send_user_tasks(self, websocket: WebSocket, user_id: int, db: Session = None):
        """发送用户任务列表"""
        if db is None:
            db = SessionLocal()
            should_close_db = True
        else:
            should_close_db = False
            
        try:
            tasks = db.query(ScanTask).filter(ScanTask.triggered_by == user_id).order_by(ScanTask.created_at.desc()).limit(10).all()
            
            tasks_data = []
            for task in tasks:
                tasks_data.append({
                    "task_id": task.task_id,
                    "job_name": task.job_name,
                    "status": task.status,
                    "jenkins_build_number": task.jenkins_build_number,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                })
            
            await websocket.send_text(json.dumps({
                "type": "tasks_list",
                "data": tasks_data
            }))
            
        except Exception as e:
            logger.error(f"Failed to send user tasks: {str(e)}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Failed to get tasks"
            }))
        finally:
            if should_close_db:
                db.close()
    
    async def _cancel_task(self, websocket: WebSocket, user_id: int, task_id: str):
        """取消任务"""
        # 这里可以实现任务取消逻辑
        # 目前只是返回一个响应
        await websocket.send_text(json.dumps({
            "type": "task_cancelled",
            "task_id": task_id,
            "message": "Task cancellation requested"
        }))

# 全局连接管理器实例
manager = ConnectionManager()