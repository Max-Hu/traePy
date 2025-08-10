from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional

from app.services.oracle_service import OracleService
from app.services.jenkins_service import JenkinsService

router = APIRouter(tags=["REST API"])

# Create service instances
oracle_service = OracleService()
jenkins_service = JenkinsService()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Service is running"}

@router.get("/oracle/tables")
async def get_oracle_tables():
    """Get list of tables in Oracle database"""
    try:
        tables = oracle_service.get_tables()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tables: {str(e)}"
        )

@router.get("/oracle/tables/{table_name}/data")
async def get_table_data(table_name: str, limit: int = 10, offset: int = 0):
    """Get data from specified table"""
    try:
        data = oracle_service.get_table_data(table_name, limit, offset)
        return {"table_name": table_name, "data": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get table data: {str(e)}"
        )

@router.get("/jenkins/jobs")
async def get_jenkins_jobs():
    """Get list of jobs on Jenkins server"""
    try:
        jobs = jenkins_service.get_jobs()
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Jenkins jobs: {str(e)}"
        )

@router.post("/jenkins/jobs/{job_name}/build")
async def trigger_jenkins_job(job_name: str, parameters: Optional[Dict[str, Any]] = None):
    """Trigger Jenkins job build"""
    try:
        build_number = jenkins_service.build_job(job_name, parameters)
        return {"job": job_name, "build_number": build_number, "status": "triggered"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger Jenkins job: {str(e)}"
        )