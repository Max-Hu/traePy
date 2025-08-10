from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import asyncio

from app.database import get_db
from app.models.database import User, ScanTask
from app.auth.jwt_auth import get_current_user
from app.services.jenkins_service import JenkinsService
from app.websocket.manager import manager
from app.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(tags=["Scan Tasks"])

# 创建Jenkins服务实例
jenkins_service = JenkinsService()

# Pydantic模型
class ScanTaskCreate(BaseModel):
    job_name: str
    parameters: Optional[Dict[str, Any]] = None

class ScanTaskResponse(BaseModel):
    id: int
    task_id: str
    job_name: str
    jenkins_build_number: Optional[int]
    status: str
    triggered_by: int
    parameters: Optional[str]
    result: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

async def monitor_task_status(task_id: str, job_name: str, build_number: int):
    """后台任务：监控Jenkins任务状态并更新数据库"""
    db = SessionLocal()
    try:
        # 获取任务记录
        task = db.query(ScanTask).filter(ScanTask.task_id == task_id).first()
        if not task:
            logger.error(f"Task not found: {task_id}")
            return
        
        # 监控任务状态
        max_attempts = 300  # 最多监控5分钟
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # 获取构建状态
                build_status = jenkins_service.get_build_status(job_name, build_number)
                
                # 更新任务状态
                if build_status["building"]:
                    if task.status != "running":
                        task.status = "running"
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        
                        # 通过WebSocket通知用户
                        await manager.send_task_update(task)
                        logger.info(f"Task {task_id} status updated to running")
                else:
                    # 任务完成
                    result = build_status["result"]
                    if result == "SUCCESS":
                        task.status = "completed"
                    elif result == "FAILURE":
                        task.status = "failed"
                    else:
                        task.status = "failed"  # 其他状态也视为失败
                    
                    task.result = json.dumps(build_status)
                    task.completed_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # 通过WebSocket通知用户
                    await manager.send_task_update(task)
                    logger.info(f"Task {task_id} completed with status: {task.status}")
                    break
                
                # 等待1秒后再次检查
                await asyncio.sleep(1)
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error monitoring task {task_id}: {str(e)}")
                await asyncio.sleep(5)  # 出错时等待更长时间
                attempt += 5
        
        # 如果超时仍未完成，标记为超时
        if attempt >= max_attempts:
            task.status = "timeout"
            task.updated_at = datetime.utcnow()
            db.commit()
            await manager.send_task_update(task)
            logger.warning(f"Task {task_id} monitoring timeout")
            
    except Exception as e:
        logger.error(f"Failed to monitor task {task_id}: {str(e)}")
    finally:
        db.close()

from app.database import SessionLocal

@router.post("/trigger", response_model=ScanTaskResponse)
async def trigger_scan_task(
    task_data: ScanTaskCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """触发扫描任务"""
    logger.info(f"User {current_user.username} triggering scan task: {task_data.job_name}")
    
    try:
        # 创建任务记录
        scan_task = ScanTask(
            job_name=task_data.job_name,
            triggered_by=current_user.id,
            parameters=json.dumps(task_data.parameters) if task_data.parameters else None,
            status="pending"
        )
        
        db.add(scan_task)
        db.commit()
        db.refresh(scan_task)
        
        # 触发Jenkins任务
        try:
            build_number = jenkins_service.build_job(task_data.job_name, task_data.parameters)
            
            # 更新任务记录
            scan_task.jenkins_build_number = build_number
            scan_task.status = "triggered" if build_number > 0 else "failed"
            scan_task.updated_at = datetime.utcnow()
            db.commit()
            
            # 如果成功触发，启动后台监控任务
            if build_number > 0:
                background_tasks.add_task(
                    monitor_task_status,
                    scan_task.task_id,
                    task_data.job_name,
                    build_number
                )
                logger.info(f"Scan task triggered successfully: {scan_task.task_id}")
            else:
                logger.error(f"Failed to get build number for task: {scan_task.task_id}")
            
            # 通过WebSocket通知用户
            await manager.send_task_update(scan_task)
            
        except Exception as jenkins_error:
            # Jenkins触发失败，更新任务状态
            scan_task.status = "failed"
            scan_task.result = json.dumps({"error": str(jenkins_error)})
            scan_task.updated_at = datetime.utcnow()
            db.commit()
            
            # 通过WebSocket通知用户
            await manager.send_task_update(scan_task)
            
            logger.error(f"Jenkins job trigger failed: {str(jenkins_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to trigger Jenkins job: {str(jenkins_error)}"
            )
        
        return scan_task
        
    except Exception as e:
        logger.error(f"Failed to create scan task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scan task: {str(e)}"
        )

@router.get("/tasks", response_model=List[ScanTaskResponse])
async def get_user_tasks(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的扫描任务列表"""
    logger.info(f"User {current_user.username} requesting task list")
    
    tasks = db.query(ScanTask).filter(
        ScanTask.triggered_by == current_user.id
    ).order_by(
        ScanTask.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return tasks

@router.get("/tasks/{task_id}", response_model=ScanTaskResponse)
async def get_task_detail(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取特定任务的详细信息"""
    logger.info(f"User {current_user.username} requesting task detail: {task_id}")
    
    task = db.query(ScanTask).filter(
        ScanTask.task_id == task_id,
        ScanTask.triggered_by == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task

@router.get("/jobs")
async def get_available_jobs(current_user: User = Depends(get_current_user)):
    """获取可用的Jenkins任务列表"""
    logger.info(f"User {current_user.username} requesting available jobs")
    
    try:
        jobs = jenkins_service.get_jobs()
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        logger.error(f"Failed to get Jenkins jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available jobs: {str(e)}"
        )