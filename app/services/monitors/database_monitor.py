import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from apscheduler.jobstores.base import JobLookupError

from .base_monitor import BaseMonitor
from app.models.database import MonitorTask
from app.logger import logger

class DatabaseMonitor(BaseMonitor):
    """Database service monitor implementation"""
    
    @property
    def service_type(self) -> str:
        return "database"
    
    async def schedule_monitor_job(self, task: MonitorTask) -> None:
        """Schedule database monitoring job"""
        try:
            job_id = f"db_monitor_{task.task_id}"
            
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
            logger.error(f"Failed to schedule database monitoring job for task {task.task_id}: {str(e)}")
            raise
    
    async def check_service_status(self, task: MonitorTask, db: Session) -> Dict[str, Any]:
        """Check database service status"""
        try:
            # Parse monitor_url to get database connection info
            # Format: "database://user:pass@host:port/dbname?query=SELECT 1"
            db_url = task.monitor_url
            
            # Extract query from URL parameters
            if "?query=" in db_url:
                connection_url, query = db_url.split("?query=", 1)
            else:
                connection_url = db_url
                query = "SELECT 1"  # Default health check query
            
            # Create database engine
            engine = create_engine(connection_url, pool_timeout=5, pool_recycle=3600)
            
            start_time = datetime.utcnow()
            
            # Execute query
            with engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            return {
                "status": "success",
                "query": query,
                "row_count": len(rows),
                "response_time_seconds": response_time,
                "timestamp": datetime.utcnow().isoformat(),
                "data": [dict(row._mapping) for row in rows] if rows else []
            }
            
        except Exception as e:
            return {
                "error": f"Database check failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def check_conditions(self, response_data: Dict[str, Any], 
                             conditions_json: str) -> bool:
        """Check database response conditions"""
        if not conditions_json or "error" in response_data:
            return False
        
        try:
            conditions = json.loads(conditions_json)
            
            # Check row count condition
            if "min_row_count" in conditions:
                if response_data.get("row_count", 0) < conditions["min_row_count"]:
                    return False
            
            if "max_row_count" in conditions:
                if response_data.get("row_count", 0) > conditions["max_row_count"]:
                    return False
            
            # Check response time condition
            if "max_response_time" in conditions:
                response_time = response_data.get("response_time_seconds", float('inf'))
                if response_time > conditions["max_response_time"]:
                    return False
            
            # Check data field conditions
            if "data_fields" in conditions and "data" in response_data:
                data = response_data["data"]
                if data:  # If there's data to check
                    for field_path, expected_value in conditions["data_fields"].items():
                        # Check first row data
                        field_value = data[0]
                        for key in field_path.split("."):
                            if isinstance(field_value, dict) and key in field_value:
                                field_value = field_value[key]
                            else:
                                return False
                        
                        if field_value != expected_value:
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking database conditions: {str(e)}")
            return False
    
    async def complete_monitoring(self, task: MonitorTask, status: str, 
                                result_data: Dict[str, Any], db: Session) -> None:
        """Complete database monitoring task"""
        try:
            # Update task status
            task.status = status
            task.completed_at = datetime.utcnow()
            task.result = json.dumps(result_data)
            
            # Remove scheduled job
            job_id = f"db_monitor_{task.task_id}"
            try:
                self.scheduler.remove_job(job_id)
            except JobLookupError:
                pass
            
            db.commit()
            
            logger.info(f"Completed database monitoring task {task.task_id} with status: {status}")
            
        except Exception as e:
            logger.error(f"Error completing database monitoring task {task.task_id}: {str(e)}")
            raise