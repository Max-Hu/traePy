from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status, Depends
from sqlalchemy.orm import Session
import json
import uuid
from typing import Optional

from app.websocket.manager import manager
from app.auth.jwt_auth import verify_token
from app.models.database import User
from app.database import SessionLocal, get_db
from app.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(tags=["WebSocket"])

async def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """从JWT token获取用户信息"""
    try:
        payload = verify_token(token)
        username = payload.get("sub")
        if not username:
            return None
        
        user = db.query(User).filter(User.username == username).first()
        return user
    except Exception as e:
        logger.error(f"Failed to get user from token: {str(e)}")
        return None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...), db: Session = Depends(get_db)):
    """WebSocket连接端点"""
    connection_id = str(uuid.uuid4())
    
    try:
        # 验证JWT token
        user = await get_user_from_token(token, db)
        if not user:
            logger.warning(f"WebSocket connection rejected: invalid token")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        if not user.is_active:
            logger.warning(f"WebSocket connection rejected: inactive user {user.username}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # 建立连接
        await manager.connect(websocket, user, connection_id, db)
        
        # 发送连接成功消息
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "connection_id": connection_id,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "message": "WebSocket connection established successfully"
        }))
        
        # 监听客户端消息
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await manager.handle_client_message(websocket, connection_id, message, db)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from connection {connection_id}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error handling message from connection {connection_id}: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: connection_id={connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        manager.disconnect(connection_id, db)

@router.get("/connections")
async def get_active_connections():
    """获取活跃连接数（调试用）"""
    total_connections = sum(len(connections) for connections in manager.active_connections.values())
    return {
        "total_connections": total_connections,
        "users_connected": len(manager.active_connections),
        "connections_by_user": {user_id: len(connections) for user_id, connections in manager.active_connections.items()}
    }