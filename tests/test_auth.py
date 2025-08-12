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

def test_password_hashing():
    """测试密码哈希功能"""
    from app.auth.jwt_auth import get_password_hash, verify_password
    
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    # 验证哈希后的密码不等于原密码
    assert hashed != password
    # 验证哈希后的密码长度合理
    assert len(hashed) > 50
    # 验证密码验证功能
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_create_access_token_default_expiry():
    """测试创建JWT token（使用默认过期时间）"""
    from app.auth.jwt_auth import create_access_token, verify_token
    from datetime import datetime, timedelta
    
    data = {"sub": "testuser", "user_id": 1}
    token = create_access_token(data)
    
    # 验证token不为空
    assert token is not None
    assert len(token) > 0
    
    # 验证token可以被解码
    payload = verify_token(token)
    assert payload["sub"] == "testuser"
    assert payload["user_id"] == 1
    assert "exp" in payload
    
    # 验证过期时间设置正确（应该是默认的30分钟）
    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    time_diff = exp_time - now
    # 允许1分钟的误差
    assert timedelta(minutes=29) <= time_diff <= timedelta(minutes=31)

def test_create_access_token_custom_expiry():
    """测试创建JWT token（使用自定义过期时间）- 第33行逻辑测试"""
    from app.auth.jwt_auth import create_access_token, verify_token
    from datetime import datetime, timedelta
    
    data = {"sub": "testuser", "user_id": 1}
    custom_expires = timedelta(hours=2)  # 自定义2小时过期
    token = create_access_token(data, expires_delta=custom_expires)
    
    # 验证token可以被解码
    payload = verify_token(token)
    assert payload["sub"] == "testuser"
    
    # 验证自定义过期时间设置正确
    exp_time = datetime.fromtimestamp(payload["exp"])
    now = datetime.utcnow()
    time_diff = exp_time - now
    # 允许1分钟的误差
    assert timedelta(hours=1, minutes=59) <= time_diff <= timedelta(hours=2, minutes=1)

def test_verify_token_expired():
    """测试验证过期的JWT token"""
    from app.auth.jwt_auth import create_access_token, verify_token
    from datetime import timedelta
    from fastapi import HTTPException
    
    data = {"sub": "testuser"}
    # 创建一个已过期的token（过期时间为-1分钟）
    expired_token = create_access_token(data, expires_delta=timedelta(minutes=-1))
    
    # 验证过期token会抛出异常
    with pytest.raises(HTTPException) as exc_info:
        verify_token(expired_token)
    
    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)

def test_verify_token_invalid_signature():
    """测试验证无效签名的JWT token"""
    from app.auth.jwt_auth import verify_token
    from fastapi import HTTPException
    
    # 使用无效的token
    invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciIsImV4cCI6OTk5OTk5OTk5OX0.invalid_signature"
    
    # 验证无效token会抛出异常
    with pytest.raises(HTTPException) as exc_info:
        verify_token(invalid_token)
    
    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in str(exc_info.value.detail)

def test_authenticate_user_success():
    """测试用户认证成功"""
    from app.auth.jwt_auth import authenticate_user
    
    db = TestingSessionLocal()
    
    # 清理并创建测试用户
    db.query(User).filter(User.username == "auth_test_user").delete()
    db.commit()
    
    user = User(
        username="auth_test_user",
        email="auth_test@example.com",
        hashed_password=get_password_hash("auth_test_password"),
        is_active=True
    )
    db.add(user)
    db.commit()
    
    # 测试认证成功
    authenticated_user = authenticate_user(db, "auth_test_user", "auth_test_password")
    assert authenticated_user is not None
    assert authenticated_user.username == "auth_test_user"
    
    db.close()

def test_authenticate_user_failure():
    """测试用户认证失败"""
    from app.auth.jwt_auth import authenticate_user
    
    db = TestingSessionLocal()
    
    # 测试用户不存在
    result = authenticate_user(db, "nonexistent_user", "password")
    assert result is None
    
    # 创建测试用户
    db.query(User).filter(User.username == "auth_fail_user").delete()
    db.commit()
    
    user = User(
        username="auth_fail_user",
        email="auth_fail@example.com",
        hashed_password=get_password_hash("correct_password"),
        is_active=True
    )
    db.add(user)
    db.commit()
    
    # 测试密码错误
    result = authenticate_user(db, "auth_fail_user", "wrong_password")
    assert result is None
    
    db.close()

def test_get_current_user_inactive_user():
    """测试获取非活跃用户信息"""
    from app.auth.jwt_auth import create_access_token
    
    db = TestingSessionLocal()
    
    # 创建非活跃用户
    db.query(User).filter(User.username == "inactive_user").delete()
    db.commit()
    
    user = User(
        username="inactive_user",
        email="inactive@example.com",
        hashed_password=get_password_hash("password"),
        is_active=False  # 设置为非活跃
    )
    db.add(user)
    db.commit()
    db.close()
    
    # 创建token
    token = create_access_token({"sub": "inactive_user"})
    
    # 尝试获取用户信息
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "Inactive user" in response.json()["detail"]

def test_get_current_user_nonexistent_user():
    """测试获取不存在用户的信息"""
    from app.auth.jwt_auth import create_access_token
    
    # 创建包含不存在用户的token
    token = create_access_token({"sub": "nonexistent_user_12345"})
    
    # 尝试获取用户信息
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 401
    assert "User not found" in response.json()["detail"]

def test_token_without_sub_claim():
    """测试没有sub声明的token"""
    from app.auth.jwt_auth import create_access_token
    
    # 创建没有sub声明的token
    token = create_access_token({"user_id": 1})  # 缺少sub字段
    
    # 尝试获取用户信息
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]

def test_create_token_with_empty_data():
    """测试使用空数据创建token"""
    from app.auth.jwt_auth import create_access_token
    
    # 测试空字典
    with pytest.raises(ValueError) as exc_info:
        create_access_token({})
    assert "Token data cannot be empty" in str(exc_info.value)
    
    # 测试None
    with pytest.raises(ValueError) as exc_info:
        create_access_token(None)
    assert "Token data cannot be empty" in str(exc_info.value)

def test_verify_token_with_empty_token():
    """测试验证空token"""
    from app.auth.jwt_auth import verify_token
    
    # 测试空字符串
    with pytest.raises(ValueError) as exc_info:
        verify_token("")
    assert "Token cannot be empty" in str(exc_info.value)
    
    # 测试空白字符串
    with pytest.raises(ValueError) as exc_info:
        verify_token("   ")
    assert "Token cannot be empty" in str(exc_info.value)
    
    # 测试None
    with pytest.raises(ValueError) as exc_info:
        verify_token(None)
    assert "Token cannot be empty" in str(exc_info.value)

def test_password_hashing_with_empty_password():
    """测试使用空密码进行哈希"""
    from app.auth.jwt_auth import get_password_hash
    
    # 测试空字符串
    with pytest.raises(ValueError) as exc_info:
        get_password_hash("")
    assert "Password cannot be empty" in str(exc_info.value)
    
    # 测试None
    with pytest.raises(ValueError) as exc_info:
        get_password_hash(None)
    assert "Password cannot be empty" in str(exc_info.value)

def test_password_verification_with_empty_params():
    """测试使用空参数进行密码验证"""
    from app.auth.jwt_auth import verify_password, get_password_hash
    
    hashed = get_password_hash("test_password")
    
    # 测试空密码
    with pytest.raises(ValueError) as exc_info:
        verify_password("", hashed)
    assert "Password and hash cannot be empty" in str(exc_info.value)
    
    # 测试空哈希
    with pytest.raises(ValueError) as exc_info:
        verify_password("test_password", "")
    assert "Password and hash cannot be empty" in str(exc_info.value)
    
    # 测试None参数
    with pytest.raises(ValueError) as exc_info:
        verify_password(None, hashed)
    assert "Password and hash cannot be empty" in str(exc_info.value)

def test_authenticate_user_with_empty_params():
    """测试使用空参数进行用户认证"""
    from app.auth.jwt_auth import authenticate_user
    
    db = TestingSessionLocal()
    
    # 测试空用户名
    with pytest.raises(ValueError) as exc_info:
        authenticate_user(db, "", "password")
    assert "Username cannot be empty" in str(exc_info.value)
    
    # 测试空密码
    with pytest.raises(ValueError) as exc_info:
        authenticate_user(db, "username", "")
    assert "Password cannot be empty" in str(exc_info.value)
    
    # 测试None参数
    with pytest.raises(ValueError) as exc_info:
        authenticate_user(db, None, "password")
    assert "Username cannot be empty" in str(exc_info.value)
    
    db.close()

def test_authenticate_user_with_inactive_user():
    """测试认证非活跃用户"""
    from app.auth.jwt_auth import authenticate_user
    
    db = TestingSessionLocal()
    
    # 创建非活跃用户
    db.query(User).filter(User.username == "inactive_auth_user").delete()
    db.commit()
    
    user = User(
        username="inactive_auth_user",
        email="inactive_auth@example.com",
        hashed_password=get_password_hash("password"),
        is_active=False
    )
    db.add(user)
    db.commit()
    
    # 尝试认证非活跃用户
    result = authenticate_user(db, "inactive_auth_user", "password")
    assert result is None
    
    db.close()

def test_token_with_iat_claim():
    """测试token包含iat（issued at）声明"""
    from app.auth.jwt_auth import create_access_token, verify_token
    from datetime import datetime
    
    data = {"sub": "testuser"}
    token = create_access_token(data)
    
    payload = verify_token(token)
    assert "iat" in payload
    
    # 验证iat时间戳合理（应该是当前时间附近）
    iat_time = datetime.fromtimestamp(payload["iat"])
    now = datetime.utcnow()
    time_diff = abs((now - iat_time).total_seconds())
    assert time_diff < 60  # 允许1分钟误差

def test_weak_password_warning():
    """测试弱密码警告（不会阻止哈希，但会记录警告）"""
    from app.auth.jwt_auth import get_password_hash
    
    # 弱密码仍然可以被哈希，但会记录警告
    weak_password = "123"
    hashed = get_password_hash(weak_password)
    
    assert hashed is not None
    assert len(hashed) > 50  # bcrypt哈希长度检查