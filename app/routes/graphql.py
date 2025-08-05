import strawberry
from typing import List, Dict, Any, Optional
from strawberry.scalars import JSON

from app.services.oracle_service import OracleService
from app.services.jenkins_service import JenkinsService
from app.models.schema import Table, TableData, Job, BuildResult
from app.logger import setup_logger

# 初始化日志记录器
logger = setup_logger(__name__)

# Create service instances
oracle_service = OracleService()
jenkins_service = JenkinsService()

@strawberry.type
class Query:
    """GraphQL query root type"""
    
    @strawberry.field(description="Health check")
    def health(self) -> str:
        logger.debug("GraphQL health check requested")
        return "Service is healthy"
    
    @strawberry.field(description="Get list of tables in Oracle database")
    def oracle_tables(self) -> List[Table]:
        logger.info("GraphQL query: oracle_tables requested")
        tables = oracle_service.get_tables()
        logger.info(f"GraphQL query: oracle_tables returned {len(tables)} tables")
        return [Table(name=table) for table in tables]
    
    @strawberry.field(description="Get data from specified table")
    def table_data(
        self, 
        table_name: str, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[TableData]:
        logger.info(f"GraphQL query: table_data requested for table {table_name}, limit={limit}, offset={offset}")
        data = oracle_service.get_table_data(table_name, limit, offset)
        logger.info(f"GraphQL query: table_data returned {len(data)} rows for table {table_name}")
        return [TableData(table_name=table_name, data=row) for row in data]
    
    @strawberry.field(description="Get list of jobs on Jenkins server")
    def jenkins_jobs(self) -> List[Job]:
        logger.info("GraphQL query: jenkins_jobs requested")
        jobs = jenkins_service.get_jobs()
        logger.info(f"GraphQL query: jenkins_jobs returned {len(jobs)} jobs")
        return [Job(name=job["name"], url=job["url"], status=job["status"]) for job in jobs]

@strawberry.input
class BuildJobInput:
    """触发Jenkins任务构建的输入"""
    job_name: str
    parameters: Optional[JSON] = None

@strawberry.type
class Mutation:
    """GraphQL mutation root type"""
    
    @strawberry.mutation(description="Trigger Jenkins job build")
    def build_job(self, input: BuildJobInput) -> BuildResult:
        logger.info(f"GraphQL mutation: build_job requested for job {input.job_name}")
        if input.parameters:
            logger.debug(f"GraphQL mutation: build_job parameters: {input.parameters}")
        
        build_number = jenkins_service.build_job(input.job_name, input.parameters)
        status = "triggered" if build_number > 0 else "failed"
        
        logger.info(f"GraphQL mutation: build_job completed for job {input.job_name}, build_number={build_number}, status={status}")
        
        return BuildResult(
            job_name=input.job_name,
            build_number=build_number,
            status=status
        )

# 创建GraphQL模式
schema = strawberry.Schema(query=Query, mutation=Mutation)