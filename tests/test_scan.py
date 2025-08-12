import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.database import Base, User, ScanTask
from app.auth.jwt_auth import get_password_hash, create_access_token

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
    db.query(User).filter(User.username == "scantest").delete()
    db.commit()
    
    # 创建测试用户
    user = User(
        username="scantest",
        email="scantest@example.com",
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

@pytest.fixture
def auth_headers(test_user_and_token):
    """获取认证头"""
    user, token = test_user_and_token
    return {"Authorization": f"Bearer {token}"}

@patch('app.routes.scan.jenkins_service')
def test_get_available_jobs(mock_jenkins_service, auth_headers):
    """测试获取可用的Jenkins任务列表"""
    # Mock Jenkins服务返回
    mock_jenkins_service.get_jobs.return_value = [
        {"name": "test-job-1", "url": "http://jenkins/job/test-job-1", "status": "success"},
        {"name": "test-job-2", "url": "http://jenkins/job/test-job-2", "status": "failed"}
    ]
    
    response = client.get("/api/scan/jobs", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "count" in data
    assert data["count"] == 2
    assert len(data["jobs"]) == 2
    assert data["jobs"][0]["name"] == "test-job-1"

@patch('app.routes.scan.jenkins_service')
def test_get_available_jobs_jenkins_error(mock_jenkins_service, auth_headers):
    """Test getting job list when Jenkins service error occurs"""
    # Mock Jenkins service throwing exception
    mock_jenkins_service.get_jobs.side_effect = Exception("Jenkins connection failed")
    
    response = client.get("/api/scan/jobs", headers=auth_headers)
    
    assert response.status_code == 500
    assert "Failed to get available jobs" in response.json()["detail"]

@patch('app.routes.scan.jenkins_service')
@patch('app.routes.scan.manager')
def test_trigger_scan_task_success(mock_manager, mock_jenkins_service, test_user_and_token, auth_headers):
    """测试成功触发扫描任务"""
    user, token = test_user_and_token
    
    # Mock Jenkins服务返回
    mock_jenkins_service.build_job.return_value = 123
    
    # Mock WebSocket管理器 - 设置为异步函数
    from unittest.mock import AsyncMock
    mock_manager.send_task_update = AsyncMock()
    
    task_data = {
        "job_name": "test-scan-job",
        "parameters": {"param1": "value1"}
    }
    
    response = client.post("/api/scan/trigger", json=task_data, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "task_id" in data
    assert data["job_name"] == "test-scan-job"
    assert data["jenkins_build_number"] == 123
    assert data["status"] == "triggered"
    assert data["triggered_by"] == user.id
    
    # 验证Jenkins服务被调用
    mock_jenkins_service.build_job.assert_called_once_with(
        "test-scan-job", {"param1": "value1"}
    )
    
    # 验证WebSocket通知被发送
    mock_manager.send_task_update.assert_called()

@patch('app.routes.scan.jenkins_service')
@patch('app.routes.scan.manager')
def test_trigger_scan_task_jenkins_failure(mock_manager, mock_jenkins_service, test_user_and_token, auth_headers):
    """测试Jenkins触发失败的情况"""
    user, token = test_user_and_token
    
    # Mock Jenkins服务抛出异常
    mock_jenkins_service.build_job.side_effect = Exception("Jenkins connection failed")
    
    # Mock WebSocket管理器 - 设置为异步函数
    from unittest.mock import AsyncMock
    mock_manager.send_task_update = AsyncMock()
    
    task_data = {
        "job_name": "failing-job"
    }
    
    response = client.post("/api/scan/trigger", json=task_data, headers=auth_headers)
    
    assert response.status_code == 500
    response_data = response.json()
    # 检查错误信息是否包含Jenkins相关错误
    assert "Jenkins connection failed" in str(response_data) or "Failed to trigger Jenkins job" in response_data.get("detail", "")
    
    # 验证任务记录仍然被创建，但状态为failed
    db = TestingSessionLocal()
    task = db.query(ScanTask).filter(
        ScanTask.job_name == "failing-job",
        ScanTask.triggered_by == user.id
    ).first()
    
    assert task is not None
    assert task.status == "failed"
    assert "Jenkins connection failed" in task.result or "Failed to trigger Jenkins job" in task.result
    
    db.close()

def test_trigger_scan_task_without_auth():
    """Test triggering scan task without authentication"""
    task_data = {
        "job_name": "test-job"
    }
    
    response = client.post("/api/scan/trigger", json=task_data)
    
    assert response.status_code == 403  # FastAPI HTTPBearer 返回403

def test_get_user_tasks(test_user_and_token, auth_headers):
    """Test getting user task list"""
    user, token = test_user_and_token
    
    # Create test task
    db = TestingSessionLocal()
    
    # Clean up existing tasks
    db.query(ScanTask).filter(ScanTask.triggered_by == user.id).delete()
    db.commit()
    
    # 创建测试任务
    task1 = ScanTask(
        job_name="test-job-1",
        triggered_by=user.id,
        status="completed",
        jenkins_build_number=100
    )
    task2 = ScanTask(
        job_name="test-job-2",
        triggered_by=user.id,
        status="running",
        jenkins_build_number=101
    )
    
    db.add(task1)
    db.add(task2)
    db.commit()
    db.close()
    
    response = client.get("/api/scan/tasks", headers=auth_headers)
    
    assert response.status_code == 200
    tasks = response.json()
    
    assert len(tasks["items"]) == 2
    # Tasks should be sorted by creation time in descending order
    assert tasks["items"][0]["job_name"] == "test-job-2"  # Latest task
    assert tasks["items"][1]["job_name"] == "test-job-1"

def test_get_user_tasks_with_pagination(test_user_and_token, auth_headers):
    """Test getting user task list with pagination"""
    user, token = test_user_and_token
    
    # Create multiple test tasks
    db = TestingSessionLocal()
    
    # Clear existing tasks
    db.query(ScanTask).filter(ScanTask.triggered_by == user.id).delete()
    db.commit()
    
    # Create 5 test tasks with different statuses
    statuses = ["pending", "running", "completed", "failed", "completed"]
    for i in range(5):
        task = ScanTask(
            job_name=f"test-job-{i}",
            triggered_by=user.id,
            status=statuses[i]
        )
        db.add(task)
    
    db.commit()
    db.close()
    
    # Test first page
    response = client.get("/api/scan/tasks?limit=2&offset=0", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Verify pagination response structure
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "total_pages" in data
    assert "has_next" in data
    assert "has_prev" in data
    
    # Verify pagination values
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["per_page"] == 2
    assert data["total_pages"] == 3
    assert data["has_next"] is True
    assert data["has_prev"] is False
    
    # Test second page
    response = client.get("/api/scan/tasks?limit=2&offset=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2
    assert data["has_next"] is True
    assert data["has_prev"] is True
    
    # Test last page
    response = client.get("/api/scan/tasks?limit=2&offset=4", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["page"] == 3
    assert data["has_next"] is False
    assert data["has_prev"] is True

def test_get_user_tasks_with_status_filter(test_user_and_token, auth_headers):
    """Test getting user task list with status filtering"""
    user, token = test_user_and_token
    
    # Create multiple test tasks
    db = TestingSessionLocal()
    
    # Clear existing tasks
    db.query(ScanTask).filter(ScanTask.triggered_by == user.id).delete()
    db.commit()
    
    # Create tasks with different statuses
    statuses = ["pending", "running", "completed", "failed", "completed"]
    for i in range(5):
        task = ScanTask(
            job_name=f"test-job-{i}",
            triggered_by=user.id,
            status=statuses[i]
        )
        db.add(task)
    
    db.commit()
    db.close()
    
    # Test filtering by completed status
    response = client.get("/api/scan/tasks?status=completed", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["status"] == "completed"
    
    # Test filtering by pending status
    response = client.get("/api/scan/tasks?status=pending", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "pending"
    
    # Test filtering with pagination
    response = client.get("/api/scan/tasks?status=completed&limit=1&offset=0", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
    assert data["has_next"] is True

def test_get_user_tasks_cursor_pagination(test_user_and_token, auth_headers):
    """Test getting user task list with cursor-based pagination"""
    user, token = test_user_and_token
    
    # Create multiple test tasks
    db = TestingSessionLocal()
    
    # Clear existing tasks
    db.query(ScanTask).filter(ScanTask.triggered_by == user.id).delete()
    db.commit()
    
    # Create 5 test tasks
    task_ids = []
    for i in range(5):
        task = ScanTask(
            job_name=f"test-job-{i}",
            triggered_by=user.id,
            status="completed"
        )
        db.add(task)
        db.flush()  # Get the ID
        task_ids.append(task.id)
    
    db.commit()
    db.close()
    
    # Test first page with cursor pagination
    response = client.get("/api/scan/tasks/cursor?limit=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Verify cursor pagination response structure
    assert "items" in data
    assert "next_cursor" in data
    assert "has_more" in data
    assert "count" in data
    
    # Verify first page values
    assert len(data["items"]) == 2
    assert data["count"] == 2
    assert data["has_more"] is True
    assert data["next_cursor"] is not None
    
    # Test second page using cursor
    next_cursor = data["next_cursor"]
    response = client.get(f"/api/scan/tasks/cursor?limit=2&cursor={next_cursor}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["has_more"] is True
    
    # Test cursor pagination with status filter
    response = client.get("/api/scan/tasks/cursor?limit=3&status=completed", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    for item in data["items"]:
        assert item["status"] == "completed"

def test_get_user_tasks_empty_result(test_user_and_token, auth_headers):
    """Test getting user task list when no tasks exist"""
    user, token = test_user_and_token
    
    # Clear all tasks for the user
    db = TestingSessionLocal()
    db.query(ScanTask).filter(ScanTask.triggered_by == user.id).delete()
    db.commit()
    db.close()
    
    # Test empty result with pagination
    response = client.get("/api/scan/tasks", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0
    assert data["has_next"] is False
    assert data["has_prev"] is False
    
    # Test empty result with cursor pagination
    response = client.get("/api/scan/tasks/cursor", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["has_more"] is False
    assert data["next_cursor"] is None

def test_get_task_detail(test_user_and_token, auth_headers):
    """Test getting specific task details"""
    user, token = test_user_and_token
    
    # 创建测试任务
    db = TestingSessionLocal()
    task = ScanTask(
        job_name="detail-test-job",
        triggered_by=user.id,
        status="completed",
        jenkins_build_number=200,
        parameters=json.dumps({"test": "param"}),
        result=json.dumps({"status": "success"})
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.task_id
    db.close()
    
    response = client.get(f"/api/scan/tasks/{task_id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["task_id"] == task_id
    assert data["job_name"] == "detail-test-job"
    assert data["status"] == "completed"
    assert data["jenkins_build_number"] == 200
    assert data["triggered_by"] == user.id

def test_get_task_detail_not_found(test_user_and_token, auth_headers):
    """Test getting details of non-existent task"""
    response = client.get("/api/scan/tasks/nonexistent-task-id", headers=auth_headers)
    
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]

def test_get_task_detail_other_user_task(test_user_and_token, auth_headers):
    """测试获取其他用户的任务详情"""
    user, token = test_user_and_token
    
    # 创建另一个用户和任务
    db = TestingSessionLocal()
    
    # 清理可能存在的重复用户
    db.query(User).filter(User.username == "otheruser").delete()
    db.query(User).filter(User.email == "other@example.com").delete()
    db.commit()
    
    other_user = User(
        username="otheruser",
        email="other@example.com",
        hashed_password=get_password_hash("password")
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    
    other_task = ScanTask(
        job_name="other-user-job",
        triggered_by=other_user.id,
        status="completed"
    )
    db.add(other_task)
    db.commit()
    db.refresh(other_task)
    other_task_id = other_task.task_id
    db.close()
    
    # 尝试访问其他用户的任务
    response = client.get(f"/api/scan/tasks/{other_task_id}", headers=auth_headers)
    
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]

def test_get_user_tasks_without_auth():
    """测试未认证时获取任务列表"""
    response = client.get("/api/scan/tasks")
    
    assert response.status_code == 403  # FastAPI HTTPBearer 返回403