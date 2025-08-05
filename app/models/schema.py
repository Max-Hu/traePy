import strawberry
from typing import Dict, Any, Optional
from strawberry.scalars import JSON

@strawberry.type
class Table:
    """Represents a table in Oracle database"""
    name: str

@strawberry.type
class TableData:
    """Represents data rows in a table"""
    table_name: str
    # Use JSON scalar type to handle dynamic fields
    # In real applications, fields can be dynamically generated based on table structure
    data: JSON

@strawberry.type
class Job:
    """Represents a Jenkins job"""
    name: str
    url: str
    status: str

@strawberry.type
class BuildResult:
    """Represents Jenkins build result"""
    job_name: str
    build_number: int
    status: str