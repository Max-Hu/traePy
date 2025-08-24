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
from app.services.monitors import BaseMonitor, HttpMonitor, DatabaseMonitor

class MonitorService:
    """Third-party service monitoring service with multi-instance support"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.instance_id = str(uuid.uuid4())  # Unique instance identifier
        self.heartbeat_timeout = 120  # 2 minutes heartbeat timeout
        self.recovery_interval = 60   # 1 minute recovery check interval
        self.task_timeout = 1800      # 30 minutes task timeout
        
        # Initialize monitor implementations
        self.monitors: Dict[str, BaseMonitor] = {
            "http": HttpMonitor(self.instance_id, self.scheduler),
            "https": HttpMonitor(self.instance_id, self.scheduler),
            "database": DatabaseMonitor(self.instance_id, self.scheduler),
            "mysql": DatabaseMonitor(self.instance_id, self.scheduler),
            "postgresql": DatabaseMonitor(self.instance_id, self.scheduler),
        }
    
    def get_monitor(self, service_name: str) -> BaseMonitor:
        """Get appropriate monitor based on service name"""
        monitor = self.monitors.get(service_name.lower())
        if not monitor:
            # Default to HTTP monitor for unknown service types
            monitor = self.monitors["http"]
        return monitor
    
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
        """Start monitoring a third-party service using appropriate monitor"""
        try:
            db = next(get_db())
            
            # Check if monitoring task already exists
            existing_task = db.query(MonitorTask).filter(
                and_(
                    MonitorTask.service_name == service_name,
                    MonitorTask.job_id == job_id,
                    MonitorTask.status.in_(['pending', 'running'])
                )
            ).first()
            
            if existing_task:
                logger.info(f"Monitoring task already exists for {service_name}:{job_id}")
                return existing_task.task_id
            
            # Create new monitoring task
            task_id = str(uuid.uuid4())
            current_time = datetime.utcnow()
            
            new_task = MonitorTask(
                task_id=task_id,
                service_name=service_name,
                job_id=job_id,
                monitor_url=monitor_url,
                success_conditions=json.dumps(success_conditions) if success_conditions else None,
                failure_conditions=json.dumps(failure_conditions) if failure_conditions else None,
                check_interval=check_interval,
                status='pending',
                assigned_instance=self.instance_id,
                created_at=current_time,
                last_heartbeat=current_time,
                timeout_at=current_time + timedelta(seconds=self.task_timeout)
            )
            
            db.add(new_task)
            db.commit()
            
            # Get appropriate monitor and schedule job
            monitor = self.get_monitor(service_name)
            await monitor.schedule_monitor_job(new_task)
            
            # Update task status to running
            new_task.status = 'running'
            db.commit()
            
            logger.info(f"Started monitoring {service_name} service for job {job_id} with task ID: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start monitoring for {service_name}:{job_id}: {str(e)}")
            raise
        finally:
            db.close()

# Create global instance
monitor_service = MonitorService()