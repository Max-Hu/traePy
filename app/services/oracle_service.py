import cx_Oracle
from typing import List, Dict, Any
from app.config import settings

class OracleService:
    """Oracle database service class providing methods for interacting with Oracle database"""
    
    def __init__(self):
        """Initialize Oracle service and set connection parameters"""
        self.connection_string = f"{settings.ORACLE_USER}/{settings.ORACLE_PASSWORD}@{settings.ORACLE_HOST}:{settings.ORACLE_PORT}/{settings.ORACLE_SERVICE}"
    
    def _get_connection(self):
        """Get database connection"""
        try:
            connection = cx_Oracle.connect(self.connection_string)
            return connection
        except cx_Oracle.Error as e:
            error, = e.args
            raise Exception(f"Oracle connection error: {error.message}")
    
    def get_tables(self) -> List[str]:
        """Get all tables in the database"""
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # Query tables owned by user
            cursor.execute("""
                SELECT table_name 
                FROM user_tables 
                ORDER BY table_name
            """)
            
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            
            return tables
        except Exception as e:
            raise Exception(f"Failed to get table list: {str(e)}")
    
    def get_table_data(self, table_name: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get data from specified table"""
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # Get table column information
            cursor.execute(f"""
                SELECT column_name 
                FROM user_tab_columns 
                WHERE table_name = '{table_name.upper()}' 
                ORDER BY column_id
            """)
            
            columns = [row[0] for row in cursor.fetchall()]
            
            if not columns:
                raise Exception(f"Table {table_name} does not exist or has no columns")
            
            # Query table data
            query = f"""
                SELECT * FROM (
                    SELECT a.*, ROWNUM rnum FROM (
                        SELECT * FROM {table_name}
                    ) a WHERE ROWNUM <= {offset + limit}
                ) WHERE rnum > {offset}
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convert results to dictionary list
            result = []
            for row in rows:
                row_dict = {"data": {}}
                for i, column in enumerate(columns):
                    row_dict["data"][column] = row[i]
                result.append(row_dict)
            
            cursor.close()
            connection.close()
            
            return result
        except Exception as e:
            raise Exception(f"Failed to get table data: {str(e)}")
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute custom SQL query"""
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            
            # Convert results to dictionary list
            result = []
            for row in rows:
                row_dict = {}
                for i, column in enumerate(columns):
                    row_dict[column] = row[i]
                result.append(row_dict)
            
            cursor.close()
            connection.close()
            
            return result
        except Exception as e:
            raise Exception(f"Failed to execute query: {str(e)}")