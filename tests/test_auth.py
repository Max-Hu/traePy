import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.database import Base, User
from app.auth.jwt_auth import get_password_hash

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
def test_user():
    """创建测试用户"""
    db = TestingSessionLocal()
    
    # 清理现有用户
    db.query(User).filter(User.username == "testuser").delete()
    db.commit()
    
    # 创建测试用户
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    return user

def test_register_user():
    """测试用户注册"""
    # 清理可能存在的测试用户
    db = TestingSessionLocal()
    db.query(User).filter(User.username == "newuser").delete()
    db.commit()
    db.close()
    
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert data["is_active"] == True
    assert "id" in data

def test_register_duplicate_username():
    """测试注册重复用户名"""
    # 先注册一个用户
    db = TestingSessionLocal()
    db.query(User).filter(User.username == "duplicate").delete()
    db.commit()
    
    user = User(
        username="duplicate",
        email="duplicate@example.com",
        hashed_password=get_password_hash("password")
    )
    db.add(user)
    db.commit()
    db.close()
    
    # 尝试注册相同用户名
    response = client.post(
        "/auth/register",
        json={
            "username": "duplicate",
            "email": "another@example.com",
            "password": "password"
        }
    )
    
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]

def test_login_success(test_user):
    """测试成功登录"""
    response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    assert data["user"]["username"] == "testuser"

def test_login_invalid_credentials():
    """测试无效凭据登录"""
    response = client.post(
        "/auth/login",
        data={
            "username": "nonexistent",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

def test_get_current_user(test_user):
    """测试获取当前用户信息"""
    # 先登录获取token
    login_response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    
    token = login_response.json()["access_token"]
    
    # 使用token获取用户信息
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["is_active"] == True

def test_get_current_user_invalid_token():
    """测试使用无效token获取用户信息"""
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]

def test_logout(test_user):
    """测试用户登出"""
    # 先登录获取token
    login_response = client.post(
        "/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword"
        }
    )
    
    token = login_response.json()["access_token"]
    
    # 登出
    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]

def test_protected_endpoint_without_token():
    """测试未携带token访问受保护的端点"""
    response = client.get("/api/scan/jobs")
    
    assert response.status_code == 403  # FastAPI HTTPBearer 返回403