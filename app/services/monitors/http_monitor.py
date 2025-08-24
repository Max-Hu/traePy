import json
import asyncio
from datetime import datetime
from typing import Dict, Any
import aiohttp
from sqlalchemy.orm import Session
from apscheduler.jobstores.base import JobLookupError

from .base_monitor import BaseMonitor
from app.models.database import MonitorTask
from app.logger import logger

class HttpMonitor(BaseMonitor):
    """HTTP service monitor implementation"""
    
    @property
    def service_type(self) -> str:
        return "http"
    
    async def schedule_monitor_job(self, task: MonitorTask) -> None:
        """Schedule HTTP monitoring job"""
        try:
            job_id = f"http_monitor_{task.task_id}"
            
            # Remove existing job if any
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            
            # Add new monitoring job
            self.scheduler.add_job(
                self.execute_check,
                'interval',
                seconds=task.check_interval,
                args=[task.task_id],
                id=job_id,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule HTTP monitoring job for task {task.task_id}: {str(e)}")
            raise
    
    async def check_service_status(self, task: MonitorTask, db: Session) -> Dict[str, Any]:
        """Check HTTP service status"""
        try:
            # Make HTTP request with timeout
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(task.monitor_url) as response:
                    response_data = {
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text(),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    # Try to parse JSON response
                    try:
                        if response.content_type == 'application/json':
                            response_data["json"] = await response.json()
                    except:
                        pass
                    
                    return response_data
                    
        except asyncio.TimeoutError:
            return {
                "error": "HTTP request timeout",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "error": f"HTTP request failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def check_conditions(self, response_data: Dict[str, Any], 
                             conditions_json: str) -> bool:
        """Check HTTP response conditions"""
        if not conditions_json or "error" in response_data:
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
            logger.error(f"Error checking HTTP conditions: {str(e)}")
            return False
    
    async def complete_monitoring(self, task: MonitorTask, status: str, 
                                result_data: Dict[str, Any], db: Session) -> None:
        """Complete HTTP monitoring task"""
        try:
            # Update task status
            task.status = status
            task.completed_at = datetime.utcnow()
            task.result = json.dumps(result_data)
            
            # Remove scheduled job
            job_id = f"http_monitor_{task.task_id}"
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            
            db.commit()
            
            logger.info(f"Completed HTTP monitoring task {task.task_id} with status: {status}")
            
        except Exception as e:
            logger.error(f"Error completing HTTP monitoring task {task.task_id}: {str(e)}")
            raise