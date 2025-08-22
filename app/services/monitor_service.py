import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import get_db
from app.models.database import MonitorTask
from app.logger import setup_logger
from app.config import settings

logger = setup_logger(__name__)

class MonitorService:
    """Third-party service monitoring service"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.active_monitors = {}  # task_id -> job_id mapping
        logger.info("Monitor service initialized")
    
    async def start_service(self):
        """Start monitoring service and recover unfinished tasks"""
        self.scheduler.start()
        await self._recover_monitoring_tasks()
        logger.info("Monitor service started")
    
    async def _recover_monitoring_tasks(self):
        """Recover unfinished monitoring tasks from database"""
        db = next(get_db())
        try:
            # Find all active monitoring tasks
            active_tasks = db.query(MonitorTask).filter(
                MonitorTask.status == "monitoring",
                MonitorTask.timeout_at > datetime.utcnow()
            ).all()
            
            for task in active_tasks:
                await self._schedule_monitor_job(task)
                logger.info(f"Recovered monitoring task: {task.task_id}")
            
            # Mark timeout tasks as timeout
            timeout_tasks = db.query(MonitorTask).filter(
                MonitorTask.status == "monitoring",
                MonitorTask.timeout_at <= datetime.utcnow()
            ).all()
            
            for task in timeout_tasks:
                task.status = "timeout"
                task.completed_at = datetime.utcnow()
                logger.info(f"Marked timeout task: {task.task_id}")
            
            db.commit()
        except Exception as e:
            logger.error(f"Failed to recover monitoring tasks: {e}")
        finally:
            db.close()
    
    async def start_monitoring(self, service_name: str, job_id: str, monitor_url: str, 
                             success_conditions: Dict = None, failure_conditions: Dict = None,
                             check_interval: int = 30) -> str:
        """Start monitoring third-party service"""
        db = next(get_db())
        try:
            # Create monitoring task
            timeout_time = datetime.utcnow() + timedelta(minutes=30)
            
            monitor_task = MonitorTask(
                service_name=service_name,
                job_id=job_id,
                monitor_url=monitor_url,
                timeout_at=timeout_time,
                check_interval=check_interval,
                success_conditions=json.dumps(success_conditions) if success_conditions else None,
                failure_conditions=json.dumps(failure_conditions) if failure_conditions else None
            )
            
            db.add(monitor_task)
            db.commit()
            db.refresh(monitor_task)
            
            # Schedule monitoring task
            await self._schedule_monitor_job(monitor_task)
            
            logger.info(f"Started monitoring task: {monitor_task.task_id} for {service_name}")
            return monitor_task.task_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to start monitoring: {e}")
            raise
        finally:
            db.close()
    
    async def _schedule_monitor_job(self, task: MonitorTask):
        """Schedule individual monitoring task"""
        job_id = f"monitor_{task.task_id}"
        
        # Remove existing task if present
        if job_id in self.active_monitors:
            self.scheduler.remove_job(job_id)
        
        # Add new monitoring task
        self.scheduler.add_job(
            func=self._check_service_status,
            trigger=IntervalTrigger(seconds=task.check_interval),
            args=[task.task_id],
            id=job_id,
            max_instances=1,
            replace_existing=True
        )
        
        self.active_monitors[task.task_id] = job_id
    
    async def _check_service_status(self, task_id: str):
        """Check service status"""
        db = next(get_db())
        try:
            task = db.query(MonitorTask).filter(MonitorTask.task_id == task_id).first()
            if not task or task.status != "monitoring":
                await self._stop_monitoring(task_id)
                return
            
            # Check if timeout
            if datetime.utcnow() > task.timeout_at:
                await self._complete_monitoring(task_id, "timeout", {"reason": "30 minutes timeout"})
                return
            
            # Send GET request to check status
            try:
                response = requests.get(task.monitor_url, timeout=10)
                response.raise_for_status()
                result_data = response.json()
                
                # Check success conditions
                if await self._check_conditions(result_data, task.success_conditions):
                    await self._complete_monitoring(task_id, "success", result_data)
                    return
                
                # Check failure conditions
                if await self._check_conditions(result_data, task.failure_conditions):
                    await self._complete_monitoring(task_id, "failed", result_data)
                    return
                
                # Update last check time
                task.updated_at = datetime.utcnow()
                db.commit()
                
                logger.debug(f"Monitoring task {task_id}: status still pending")
                
            except Exception as e:
                logger.error(f"Failed to check service status for task {task_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error in monitoring task {task_id}: {e}")
        finally:
            db.close()
    
    async def _check_conditions(self, data: Dict, conditions_json: str) -> bool:
        """Check if conditions are met"""
        if not conditions_json:
            return False
        
        try:
            conditions = json.loads(conditions_json)
            for key, expected_value in conditions.items():
                if data.get(key) == expected_value:
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to check conditions: {e}")
            return False
    
    async def _complete_monitoring(self, task_id: str, status: str, result_data: Dict):
        """Complete monitoring task"""
        db = next(get_db())
        try:
            task = db.query(MonitorTask).filter(MonitorTask.task_id == task_id).first()
            if task:
                task.status = status
                task.result = json.dumps(result_data)
                task.completed_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Completed monitoring task {task_id} with status: {status}")
            
            await self._stop_monitoring(task_id)
            
        except Exception as e:
            logger.error(f"Failed to complete monitoring task {task_id}: {e}")
        finally:
            db.close()
    
    async def _stop_monitoring(self, task_id: str):
        """Stop monitoring task"""
        job_id = self.active_monitors.get(task_id)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                del self.active_monitors[task_id]
                logger.info(f"Stopped monitoring task: {task_id}")
            except Exception as e:
                logger.error(f"Failed to stop monitoring task {task_id}: {e}")
    
    async def get_monitoring_status(self, task_id: str) -> Optional[Dict]:
        """Get monitoring task status"""
        db = next(get_db())
        try:
            task = db.query(MonitorTask).filter(MonitorTask.task_id == task_id).first()
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "service_name": task.service_name,
                "job_id": task.job_id,
                "status": task.status,
                "result": json.loads(task.result) if task.result else None,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "timeout_at": task.timeout_at.isoformat()
            }
        finally:
            db.close()
    
    async def get_all_monitoring_tasks(self, limit: int = 50) -> List[Dict]:
        """Get all monitoring tasks"""
        db = next(get_db())
        try:
            tasks = db.query(MonitorTask).order_by(MonitorTask.created_at.desc()).limit(limit).all()
            
            result = []
            for task in tasks:
                result.append({
                    "task_id": task.task_id,
                    "service_name": task.service_name,
                    "job_id": task.job_id,
                    "status": task.status,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "timeout_at": task.timeout_at.isoformat()
                })
            
            return result
        finally:
            db.close()

# Global monitoring service instance
monitor_service = MonitorService()