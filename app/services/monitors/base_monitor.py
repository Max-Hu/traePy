from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.database import MonitorTask

class BaseMonitor(ABC):
    """Abstract base class for service monitors"""
    
    def __init__(self, instance_id: str, scheduler):
        self.instance_id = instance_id
        self.scheduler = scheduler
    
    @abstractmethod
    async def schedule_monitor_job(self, task: MonitorTask) -> None:
        """Schedule monitoring job for specific service type"""
        pass
    
    @abstractmethod
    async def check_service_status(self, task: MonitorTask, db: Session) -> Dict[str, Any]:
        """Check service status and return response data"""
        pass
    
    @abstractmethod
    async def check_conditions(self, response_data: Dict[str, Any], 
                             conditions_json: str) -> bool:
        """Check if response meets specified conditions"""
        pass
    
    @abstractmethod
    async def complete_monitoring(self, task: MonitorTask, status: str, 
                                result_data: Dict[str, Any], db: Session) -> None:
        """Complete monitoring task with cleanup"""
        pass
    
    @property
    @abstractmethod
    def service_type(self) -> str:
        """Return the service type this monitor handles"""
        pass
    
    async def execute_check(self, task_id: str):
        """Common execution logic for all monitors"""
        from app.database import get_db
        from app.logger import logger
        from sqlalchemy import and_
        
        db = None
        try:
            db = next(get_db())
            
            # Get task with lock
            task = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.task_id == task_id,
                    MonitorTask.assigned_instance == self.instance_id,
                    MonitorTask.status == 'running'
                )
            ).with_for_update().first()
            
            if not task:
                logger.warning(f"Task {task_id} not found or not assigned to this instance")
                return
            
            current_time = datetime.utcnow()
            
            # Check global timeout
            if task.timeout_at <= current_time:
                await self.complete_monitoring(task, 'timeout', 
                                              {"error": "Task globally timed out"}, db)
                return
            
            # Update heartbeat
            task.last_heartbeat = current_time
            
            # Check service status using specific implementation
            response_data = await self.check_service_status(task, db)
            
            # Check success conditions
            if await self.check_conditions(response_data, task.success_conditions):
                await self.complete_monitoring(task, 'completed', response_data, db)
                return
            
            # Check failure conditions
            if await self.check_conditions(response_data, task.failure_conditions):
                await self.complete_monitoring(task, 'failed', response_data, db)
                return
            
            # Continue monitoring
            db.commit()
            
        except Exception as e:
            logger.error(f"Error in {self.service_type} monitor for task {task_id}: {str(e)}")
            if db and 'task' in locals():
                try:
                    await self.complete_monitoring(task, 'failed', 
                                                  {"error": f"Monitoring error: {str(e)}"}, db)
                except:
                    pass
        finally:
            if db:
                db.close()