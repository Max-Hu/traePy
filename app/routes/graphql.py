import strawberry
from typing import List, Dict, Any, Optional
from strawberry.scalars import JSON

from app.services.oracle_service import OracleService
from app.services.jenkins_service import JenkinsService
from app.models.schema import Table, TableData, Job, BuildResult

# Create service instances
oracle_service = OracleService()
jenkins_service = JenkinsService()

@strawberry.type
class Query:
    """GraphQL query root type"""
    
    @strawberry.field(description="Health check")
    def health(self) -> str:
        return "Service is healthy"
    
    @strawberry.field(description="Get list of tables in Oracle database")
    def oracle_tables(self) -> List[Table]:
        tables = oracle_service.get_tables()
        return [Table(name=table) for table in tables]
    
    @strawberry.field(description="Get data from specified table")
    def table_data(
        self, 
        table_name: str, 
        limit: int = 10, 
        offset: int = 0
    ) -> List[TableData]:
        data = oracle_service.get_table_data(table_name, limit, offset)
        return [TableData(table_name=table_name, data=row) for row in data]
    
    @strawberry.field(description="Get list of jobs on Jenkins server")
    def jenkins_jobs(self) -> List[Job]:
        jobs = jenkins_service.get_jobs()
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
        build_number = jenkins_service.build_job(input.job_name, input.parameters)
        return BuildResult(
            job_name=input.job_name,
            build_number=build_number,
            status="triggered" if build_number > 0 else "failed"
        )

# 创建GraphQL模式
schema = strawberry.Schema(query=Query, mutation=Mutation)