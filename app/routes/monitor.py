from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.services.monitor_service import monitor_service
from app.auth.jwt_auth import get_current_user
from app.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(tags=["monitor"])

class StartMonitorRequest(BaseModel):
    """Request model for starting monitoring"""
    service_name: str
    job_id: str
    monitor_url: str
    success_conditions: Optional[Dict[str, Any]] = None
    failure_conditions: Optional[Dict[str, Any]] = None
    check_interval: int = 30

class MonitorResponse(BaseModel):
    """Response model for monitoring operations"""
    success: bool
    message: Optional[str] = None
    task_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@router.post("/start", response_model=MonitorResponse)
async def start_monitoring(request: StartMonitorRequest, current_user=Depends(get_current_user)):
    """Start monitoring third-party service"""
    try:
        task_id = await monitor_service.start_monitoring(
            service_name=request.service_name,
            job_id=request.job_id,
            monitor_url=request.monitor_url,
            success_conditions=request.success_conditions,
            failure_conditions=request.failure_conditions,
            check_interval=request.check_interval
        )
        
        return MonitorResponse(
            success=True,
            task_id=task_id,
            message="Monitoring task started successfully"
        )
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}", response_model=MonitorResponse)
async def get_monitoring_status(task_id: str, current_user=Depends(get_current_user)):
    """Get monitoring task status"""
    try:
        status = await monitor_service.get_monitoring_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="Monitoring task not found")
        
        return MonitorResponse(
            success=True,
            data=status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=MonitorResponse)
async def list_monitoring_tasks(limit: int = 50, current_user=Depends(get_current_user)):
    """Get all monitoring tasks list"""
    try:
        tasks = await monitor_service.get_all_monitoring_tasks(limit=limit)
        
        return MonitorResponse(
            success=True,
            data={"tasks": tasks, "total": len(tasks)}
        )
            
    except Exception as e:
        logger.error(f"Failed to list monitoring tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/stop/{task_id}", response_model=MonitorResponse)
async def stop_monitoring(task_id: str, current_user=Depends(get_current_user)):
    """Stop monitoring task manually"""
    try:
        # Get task status first
        status = await monitor_service.get_monitoring_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="Monitoring task not found")
        
        if status["status"] != "monitoring":
            return MonitorResponse(
                success=True,
                message=f"Task is already {status['status']}"
            )
        
        # Stop the monitoring task
        await monitor_service._stop_monitoring(task_id)
        
        # Update task status in database
        from app.database import get_db
        from app.models.database import MonitorTask
        from datetime import datetime
        
        db = next(get_db())
        try:
            task = db.query(MonitorTask).filter(MonitorTask.task_id == task_id).first()
            if task:
                task.status = "stopped"
                task.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return MonitorResponse(
            success=True,
            message="Monitoring task stopped successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop monitoring task: {e}")
        raise HTTPException(status_code=500, detail=str(e))