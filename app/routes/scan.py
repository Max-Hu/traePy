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

# Create Jenkins service instance
jenkins_service = JenkinsService()

# Pydantic models
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

class PaginatedScanTaskResponse(BaseModel):
    items: List[ScanTaskResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

class CursorPaginatedScanTaskResponse(BaseModel):
    items: List[ScanTaskResponse]
    next_cursor: Optional[int]
    has_more: bool
    count: int

async def monitor_task_status(task_id: str, job_name: str, build_number: int):
    """Background task: Monitor Jenkins task status and update database"""
    db = SessionLocal()
    try:
        # Get task record
        task = db.query(ScanTask).filter(ScanTask.task_id == task_id).first()
        if not task:
            logger.error(f"Task not found: {task_id}")
            return
        
        # Monitor task status
        max_attempts = 300  # Monitor for maximum 5 minutes
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Get build status
                build_status = jenkins_service.get_build_status(job_name, build_number)
                
                # Update task status
                if build_status["building"]:
                    if task.status != "running":
                        task.status = "running"
                        task.updated_at = datetime.utcnow()
                        db.commit()
                        
                        # Notify user via WebSocket
                        await manager.send_task_update(task)
                        logger.info(f"Task {task_id} status updated to running")
                else:
                    # Task completed
                    result = build_status["result"]
                    if result == "SUCCESS":
                        task.status = "completed"
                    elif result == "FAILURE":
                        task.status = "failed"
                    else:
                        task.status = "failed"  # Other statuses are also considered as failure
                    
                    task.result = json.dumps(build_status)
                    task.completed_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # Notify user via WebSocket
                    await manager.send_task_update(task)
                    logger.info(f"Task {task_id} completed with status: {task.status}")
                    break
                
                # Wait 1 second before checking again
                await asyncio.sleep(1)
                attempt += 1
                
            except Exception as e:
                logger.error(f"Error monitoring task {task_id}: {str(e)}")
                await asyncio.sleep(5)  # Wait longer when error occurs
                attempt += 5
        
        # If timeout and still not completed, mark as timeout
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
    """Trigger scan task"""
    logger.info(f"User {current_user.username} triggering scan task: {task_data.job_name}")
    
    try:
        # Create task record
        scan_task = ScanTask(
            job_name=task_data.job_name,
            triggered_by=current_user.id,
            parameters=json.dumps(task_data.parameters) if task_data.parameters else None,
            status="pending"
        )
        
        db.add(scan_task)
        db.commit()
        db.refresh(scan_task)
        
        # Trigger Jenkins task
        try:
            build_number = jenkins_service.build_job(task_data.job_name, task_data.parameters)
            
            # Update task record
            scan_task.jenkins_build_number = build_number
            scan_task.status = "triggered" if build_number > 0 else "failed"
            scan_task.updated_at = datetime.utcnow()
            db.commit()
            
            # If successfully triggered, start background monitoring task
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
            
            # Notify user via WebSocket
            await manager.send_task_update(scan_task)
            
        except Exception as jenkins_error:
            # Jenkins trigger failed, update task status
            scan_task.status = "failed"
            scan_task.result = json.dumps({"error": str(jenkins_error)})
            scan_task.updated_at = datetime.utcnow()
            db.commit()
            
            # Notify user via WebSocket
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

@router.get("/tasks", response_model=PaginatedScanTaskResponse)
async def get_user_tasks(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's scan task list with pagination and filtering"""
    logger.info(f"User {current_user.username} requesting task list with limit={limit}, offset={offset}, status={status}")
    
    # Build base query
    query = db.query(ScanTask).filter(
        ScanTask.triggered_by == current_user.id
    )
    
    # Apply status filter if provided
    if status:
        query = query.filter(ScanTask.status == status)
    
    # Get total count
    total_count = query.count()
    
    # Get paginated results
    tasks = query.order_by(
        ScanTask.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    # Calculate pagination info
    page = offset // limit + 1
    total_pages = (total_count + limit - 1) // limit
    has_next = offset + limit < total_count
    has_prev = offset > 0
    
    return PaginatedScanTaskResponse(
         items=tasks,
         total=total_count,
         page=page,
         per_page=limit,
         total_pages=total_pages,
         has_next=has_next,
         has_prev=has_prev
     )

@router.get("/tasks/cursor", response_model=CursorPaginatedScanTaskResponse)
async def get_user_tasks_cursor(
    limit: int = 20,
    cursor: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's scan task list using cursor-based pagination (better for large datasets)"""
    logger.info(f"User {current_user.username} requesting task list with cursor pagination: limit={limit}, cursor={cursor}, status={status}")
    
    # Build base query
    query = db.query(ScanTask).filter(
        ScanTask.triggered_by == current_user.id
    )
    
    # Apply status filter if provided
    if status:
        query = query.filter(ScanTask.status == status)
    
    # Apply cursor filter (get records with ID less than cursor for descending order)
    if cursor:
        query = query.filter(ScanTask.id < cursor)
    
    # Get results ordered by ID descending (most recent first)
    tasks = query.order_by(
        ScanTask.id.desc()
    ).limit(limit + 1).all()  # Get one extra to check if there are more
    
    # Check if there are more results
    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:-1]  # Remove the extra record
    
    # Get next cursor (ID of the last item)
    next_cursor = tasks[-1].id if tasks else None
    
    return CursorPaginatedScanTaskResponse(
        items=tasks,
        next_cursor=next_cursor,
        has_more=has_more,
        count=len(tasks)
    )

@router.get("/tasks/{task_id}", response_model=ScanTaskResponse)
async def get_task_detail(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information of specific task"""
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