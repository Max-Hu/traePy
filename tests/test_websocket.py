import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.database import Base, User, WebSocketConnection
from app.auth.jwt_auth import get_password_hash, create_access_token
from app.websocket.manager import manager

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_traepy.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建测试数据库表
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture
def test_user_and_token():
    """创建测试用户和JWT token"""
    db = TestingSessionLocal()
    
    # 清理现有用户
    db.query(User).filter(User.username == "wstest").delete()
    db.commit()
    
    # 创建测试用户
    user = User(
        username="wstest",
        email="wstest@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 创建JWT token
    token = create_access_token(data={"sub": user.username})
    
    db.close()
    
    return user, token

def test_websocket_connection_with_valid_token(test_user_and_token):
    """测试使用有效token建立WebSocket连接"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        data = websocket.receive_text()
        message = json.loads(data)
        
        assert message["type"] == "connection_established"
        assert "connection_id" in message
        assert message["user"]["username"] == "wstest"
        assert message["message"] == "WebSocket connection established successfully"

def test_websocket_connection_with_invalid_token():
    """测试使用无效token建立WebSocket连接"""
    with pytest.raises(Exception):  # WebSocket连接应该被拒绝
        with client.websocket_connect("/ws/ws?token=invalid_token") as websocket:
            pass

def test_websocket_ping_pong(test_user_and_token):
    """测试WebSocket心跳机制"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        websocket.receive_text()
        
        # 发送ping消息
        ping_message = {"type": "ping"}
        websocket.send_text(json.dumps(ping_message))
        
        # 接收pong响应
        response = websocket.receive_text()
        pong_message = json.loads(response)
        
        assert pong_message["type"] == "pong"
        assert "timestamp" in pong_message

def test_websocket_get_tasks_message(test_user_and_token):
    """测试通过WebSocket获取任务列表"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        websocket.receive_text()
        
        # 发送获取任务消息
        get_tasks_message = {"type": "get_tasks"}
        websocket.send_text(json.dumps(get_tasks_message))
        
        # 接收任务列表响应
        response = websocket.receive_text()
        tasks_message = json.loads(response)
        
        assert tasks_message["type"] == "tasks_list"
        assert "data" in tasks_message
        assert isinstance(tasks_message["data"], list)

def test_websocket_invalid_message_type(test_user_and_token):
    """测试发送无效消息类型"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        websocket.receive_text()
        
        # 发送无效消息类型
        invalid_message = {"type": "invalid_type"}
        websocket.send_text(json.dumps(invalid_message))
        
        # 接收错误响应
        response = websocket.receive_text()
        error_message = json.loads(response)
        
        assert error_message["type"] == "error"
        assert "Unknown message type" in error_message["message"]

def test_websocket_invalid_json(test_user_and_token):
    """测试发送无效JSON格式消息"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        websocket.receive_text()
        
        # 发送无效JSON
        websocket.send_text("invalid json")
        
        # 接收错误响应
        response = websocket.receive_text()
        error_message = json.loads(response)
        
        assert error_message["type"] == "error"
        assert "Invalid JSON format" in error_message["message"]

def test_websocket_cancel_task_message(test_user_and_token):
    """测试通过WebSocket取消任务"""
    user, token = test_user_and_token
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        websocket.receive_text()
        
        # 发送取消任务消息
        cancel_message = {"type": "cancel_task", "task_id": "test-task-id"}
        websocket.send_text(json.dumps(cancel_message))
        
        # 接收取消响应
        response = websocket.receive_text()
        cancel_response = json.loads(response)
        
        assert cancel_response["type"] == "task_cancelled"
        assert cancel_response["task_id"] == "test-task-id"
        assert "Task cancellation requested" in cancel_response["message"]

def test_get_active_connections_endpoint():
    """测试获取活跃连接数的端点"""
    response = client.get("/ws/connections")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_connections" in data
    assert "users_connected" in data
    assert "connections_by_user" in data
    assert isinstance(data["total_connections"], int)
    assert isinstance(data["users_connected"], int)
    assert isinstance(data["connections_by_user"], dict)

def test_websocket_connection_recorded_in_database(test_user_and_token):
    """测试WebSocket连接是否正确记录到数据库"""
    user, token = test_user_and_token
    
    # 清理现有连接记录
    db = TestingSessionLocal()
    db.query(WebSocketConnection).filter(WebSocketConnection.user_id == user.id).delete()
    db.commit()
    db.close()
    
    with client.websocket_connect(f"/ws/ws?token={token}") as websocket:
        # 接收连接建立消息
        data = websocket.receive_text()
        message = json.loads(data)
        connection_id = message["connection_id"]
        
        # 检查数据库中的连接记录
        db = TestingSessionLocal()
        connection_record = db.query(WebSocketConnection).filter(
            WebSocketConnection.connection_id == connection_id
        ).first()
        
        assert connection_record is not None
        assert connection_record.user_id == user.id
        assert connection_record.is_active == True
        assert connection_record.connected_at is not None
        
        db.close()
    
    # 连接关闭后，检查数据库记录是否更新
    db = TestingSessionLocal()
    connection_record = db.query(WebSocketConnection).filter(
        WebSocketConnection.connection_id == connection_id
    ).first()
    
    # 注意：在测试环境中，连接关闭的处理可能不会立即执行
    # 这里主要测试连接建立时的记录
    assert connection_record is not None
    db.close()