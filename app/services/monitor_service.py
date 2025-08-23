import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.database import MonitorTask
from app.database import get_db
from app.logger import logger

class MonitorService:
    """Third-party service monitoring service with multi-instance support"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.instance_id = str(uuid.uuid4())  # Unique instance identifier
        self.heartbeat_timeout = 120  # 2 minutes heartbeat timeout
        self.recovery_interval = 60   # 1 minute recovery check interval
        self.task_timeout = 1800      # 30 minutes task timeout
        
    async def start_service(self):
        """Start monitoring service and recover existing tasks"""
        try:
            logger.info(f"Starting monitor service with instance ID: {self.instance_id}")
            
            # Start scheduler
            self.scheduler.start()
            
            # Schedule recovery job
            self.scheduler.add_job(
                self._recover_orphaned_tasks,
                'interval',
                seconds=self.recovery_interval,
                id='recovery_job',
                max_instances=1,
                coalesce=True
            )
            
            # Recover existing tasks
            await self._recover_monitoring_tasks()
            
            logger.info("Monitor service started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start monitor service: {str(e)}")
            raise
    
    async def stop_service(self):
        """Stop monitoring service"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            logger.info(f"Monitor service stopped for instance: {self.instance_id}")
        except Exception as e:
            logger.error(f"Error stopping monitor service: {str(e)}")
    
    async def _recover_monitoring_tasks(self):
        """Recover monitoring tasks on service startup"""
        try:
            db = next(get_db())
            
            # Find tasks that need recovery
            current_time = datetime.utcnow()
            timeout_threshold = current_time - timedelta(seconds=self.heartbeat_timeout)
            
            # Query tasks that need recovery
            tasks_to_recover = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.status.in_(['pending', 'running']),
                    or_(
                        MonitorTask.assigned_instance == self.instance_id,  # Tasks assigned to this instance
                        and_(
                            MonitorTask.status == 'running',
                            MonitorTask.last_heartbeat < timeout_threshold  # Orphaned tasks
                        ),
                        and_(
                            MonitorTask.status == 'pending',
                            MonitorTask.assigned_instance.is_(None)  # Unassigned pending tasks
                        )
                    ),
                    MonitorTask.timeout_at > current_time  # Not globally timed out
                )
            ).all()
            
            recovered_count = 0
            for task in tasks_to_recover:
                try:
                    # Check if task is globally timed out
                    if task.timeout_at <= current_time:
                        task.status = 'timeout'
                        task.completed_at = current_time
                        task.result = json.dumps({"error": "Task globally timed out"})
                        continue
                    
                    # Assign task to current instance
                    task.assigned_instance = self.instance_id
                    task.status = 'running'
                    task.last_heartbeat = current_time
                    
                    # Schedule monitoring job
                    await self._schedule_monitor_job(task)
                    recovered_count += 1
                    
                    logger.info(f"Recovered monitoring task: {task.task_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to recover task {task.task_id}: {str(e)}")
            
            db.commit()
            db.close()
            
            if recovered_count > 0:
                logger.info(f"Recovered {recovered_count} monitoring tasks")
                
        except Exception as e:
            logger.error(f"Failed to recover monitoring tasks: {str(e)}")
    
    async def _recover_orphaned_tasks(self):
        """Periodic job to recover orphaned tasks from failed instances"""
        try:
            db = next(get_db())
            
            current_time = datetime.utcnow()
            timeout_threshold = current_time - timedelta(seconds=self.heartbeat_timeout)
            
            # Find orphaned running tasks
            orphaned_tasks = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.status == 'running',
                    MonitorTask.last_heartbeat < timeout_threshold,
                    MonitorTask.assigned_instance != self.instance_id,
                    MonitorTask.timeout_at > current_time
                )
            ).with_for_update().all()
            
            recovered_count = 0
            for task in orphaned_tasks:
                try:
                    # Take ownership of orphaned task
                    task.assigned_instance = self.instance_id
                    task.last_heartbeat = current_time
                    task.retry_count += 1
                    
                    # Check if max retries exceeded
                    if task.retry_count > task.max_retries:
                        task.status = 'failed'
                        task.completed_at = current_time
                        task.result = json.dumps({"error": "Max retries exceeded after instance failure"})
                        logger.warning(f"Task {task.task_id} failed after max retries")
                        continue
                    
                    # Schedule monitoring job
                    await self._schedule_monitor_job(task)
                    recovered_count += 1
                    
                    logger.warning(f"Recovered orphaned task {task.task_id} from failed instance")
                    
                except Exception as e:
                    logger.error(f"Failed to recover orphaned task {task.task_id}: {str(e)}")
            
            db.commit()
            db.close()
            
            if recovered_count > 0:
                logger.info(f"Recovered {recovered_count} orphaned tasks")
                
        except Exception as e:
            logger.error(f"Failed to recover orphaned tasks: {str(e)}")
    
    async def start_monitoring(self, service_name: str, job_id: str, monitor_url: str, 
                             success_conditions: Dict[str, Any] = None, 
                             failure_conditions: Dict[str, Any] = None,
                             check_interval: int = 30) -> str:
        """Start monitoring a third-party service"""
        try:
            db = next(get_db())
            
            # Check for existing active monitoring task
            existing_task = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.service_name == service_name,
                    MonitorTask.job_id == job_id,
                    MonitorTask.status.in_(['pending', 'running'])
                )
            ).with_for_update().first()
            
            if existing_task:
                db.close()
                return existing_task.task_id
            
            # Create new monitoring task
            task_id = str(uuid.uuid4())
            current_time = datetime.utcnow()
            timeout_time = current_time + timedelta(seconds=self.task_timeout)
            
            monitor_task = MonitorTask(
                task_id=task_id,
                service_name=service_name,
                job_id=job_id,
                monitor_url=monitor_url,
                status='running',
                timeout_at=timeout_time,
                check_interval=check_interval,
                success_conditions=json.dumps(success_conditions) if success_conditions else None,
                failure_conditions=json.dumps(failure_conditions) if failure_conditions else None,
                assigned_instance=self.instance_id,
                last_heartbeat=current_time
            )
            
            db.add(monitor_task)
            db.commit()
            
            # Schedule monitoring job
            await self._schedule_monitor_job(monitor_task)
            
            db.close()
            
            logger.info(f"Started monitoring task {task_id} for {service_name}:{job_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {str(e)}")
            raise
    
    async def _schedule_monitor_job(self, task: MonitorTask):
        """Schedule a monitoring job in the scheduler"""
        try:
            job_id = f"monitor_{task.task_id}"
            
            # Remove existing job if any
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            
            # Add new monitoring job
            self.scheduler.add_job(
                self._check_service_status,
                'interval',
                seconds=task.check_interval,
                args=[task.task_id],
                id=job_id,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule monitoring job for task {task.task_id}: {str(e)}")
            raise
    
    async def _check_service_status(self, task_id: str):
        """Check third-party service status"""
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
                await self._complete_monitoring(task, 'timeout', 
                                              {"error": "Task globally timed out"}, db)
                return
            
            # Update heartbeat
            task.last_heartbeat = current_time
            
            # Make HTTP request to check service status
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(task.monitor_url) as response:
                    response_data = {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    
                    # Try to parse JSON response
                    try:
                        if response.content_type == 'application/json':
                            response_data["json"] = await response.json()
                    except:
                        pass
            
            # Check success conditions
            if await self._check_conditions(response_data, task.success_conditions):
                await self._complete_monitoring(task, 'completed', response_data, db)
                return
            
            # Check failure conditions
            if await self._check_conditions(response_data, task.failure_conditions):
                await self._complete_monitoring(task, 'failed', response_data, db)
                return
            
            # Continue monitoring
            db.commit()
            
        except asyncio.TimeoutError:
            logger.warning(f"Timeout checking service status for task {task_id}")
        except Exception as e:
            logger.error(f"Error checking service status for task {task_id}: {str(e)}")
            if db and task:
                try:
                    await self._complete_monitoring(task, 'failed', 
                                                  {"error": f"Monitoring error: {str(e)}"}, db)
                except:
                    pass
        finally:
            if db:
                db.close()
    
    async def _check_conditions(self, response_data: Dict[str, Any], 
                              conditions_json: str) -> bool:
        """Check if response meets specified conditions"""
        if not conditions_json:
            return False
        
        try:
            conditions = json.loads(conditions_json)
            
            # Check status code condition
            if "status_code" in conditions:
                expected_status = conditions["status_code"]
                if isinstance(expected_status, list):
                    if response_data["status_code"] not in expected_status:
                        return False
                else:
                    if response_data["status_code"] != expected_status:
                        return False
            
            # Check JSON field conditions
            if "json_fields" in conditions and "json" in response_data:
                json_data = response_data["json"]
                for field_path, expected_value in conditions["json_fields"].items():
                    # Support nested field access like "result.status"
                    field_value = json_data
                    for key in field_path.split("."):
                        if isinstance(field_value, dict) and key in field_value:
                            field_value = field_value[key]
                        else:
                            return False
                    
                    if field_value != expected_value:
                        return False
            
            # Check body contains condition
            if "body_contains" in conditions:
                search_text = conditions["body_contains"]
                if search_text not in response_data["body"]:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking conditions: {str(e)}")
            return False
    
    async def _complete_monitoring(self, task: MonitorTask, status: str, 
                                 result_data: Dict[str, Any], db: Session):
        """Complete monitoring task and cleanup"""
        try:
            # Update task status
            task.status = status
            task.completed_at = datetime.utcnow()
            task.result = json.dumps(result_data)
            
            # Remove scheduled job
            job_id = f"monitor_{task.task_id}"
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            
            db.commit()
            
            logger.info(f"Completed monitoring task {task.task_id} with status: {status}")
            
        except Exception as e:
            logger.error(f"Error completing monitoring task {task.task_id}: {str(e)}")
            raise
    
    async def stop_monitoring(self, task_id: str) -> bool:
        """Manually stop a monitoring task"""
        try:
            db = next(get_db())
            
            task = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.task_id == task_id,
                    MonitorTask.status == 'running'
                )
            ).with_for_update().first()
            
            if not task:
                db.close()
                return False
            
            await self._complete_monitoring(task, 'stopped', 
                                          {"message": "Manually stopped"}, db)
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop monitoring task {task_id}: {str(e)}")
            return False
    
    async def get_monitoring_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get monitoring task status"""
        try:
            db = next(get_db())
            
            task = db.query(MonitorTask).filter(
                MonitorTask.task_id == task_id
            ).first()
            
            if not task:
                db.close()
                return None
            
            result = {
                "task_id": task.task_id,
                "service_name": task.service_name,
                "job_id": task.job_id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "timeout_at": task.timeout_at.isoformat(),
                "assigned_instance": task.assigned_instance,
                "last_heartbeat": task.last_heartbeat.isoformat() if task.last_heartbeat else None,
                "retry_count": task.retry_count,
                "result": json.loads(task.result) if task.result else None
            }
            
            db.close()
            return result
            
        except Exception as e:
            logger.error(f"Failed to get monitoring status for task {task_id}: {str(e)}")
            return None
    
    async def list_monitoring_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """List monitoring tasks with optional status filter"""
        try:
            db = next(get_db())
            
            query = db.query(MonitorTask)
            if status:
                query = query.filter(MonitorTask.status == status)
            
            tasks = query.order_by(MonitorTask.created_at.desc()).all()
            
            result = []
            for task in tasks:
                result.append({
                    "task_id": task.task_id,
                    "service_name": task.service_name,
                    "job_id": task.job_id,
                    "status": task.status,
                    "created_at": task.created_at.isoformat(),
                    "assigned_instance": task.assigned_instance,
                    "last_heartbeat": task.last_heartbeat.isoformat() if task.last_heartbeat else None
                })
            
            db.close()
            return result
            
        except Exception as e:
            logger.error(f"Failed to list monitoring tasks: {str(e)}")
            return []

# Global monitor service instance
monitor_service = MonitorService()