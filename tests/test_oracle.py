import unittest
from unittest.mock import patch, MagicMock
import oracledb

from app.services.oracle_service import OracleService

class TestOracleService(unittest.TestCase):
    """Oracle service unit test class"""
    
    def setUp(self):
        """Preparation work before testing"""
        self.oracle_service = OracleService()
    
    @patch('oracledb.connect')
    def test_get_tables(self, mock_connect):
        """Test get table list functionality"""
        # Set up mock objects
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Set up mock query results
        mock_cursor.fetchall.return_value = [("TABLE1",), ("TABLE2",), ("TABLE3",)]
        
        # Call the method being tested
        tables = self.oracle_service.get_tables()
        
        # Verify results
        self.assertEqual(len(tables), 3)
        self.assertEqual(tables, ["TABLE1", "TABLE2", "TABLE3"])
        
        # Verify method calls
        mock_connect.assert_called_once()
        mock_connection.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('oracledb.connect')
    def test_get_table_data(self, mock_connect):
        """Test get table data functionality"""
        # Set up mock objects
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Set up mock query results - column information
        mock_cursor.fetchall.side_effect = [
            [("ID",), ("NAME",), ("VALUE",)],  # Column information query results
            [(1, "Test1", 100), (2, "Test2", 200)]  # Data query results
        ]
        
        # Call the method being tested
        table_data = self.oracle_service.get_table_data("TEST_TABLE", 2, 0)
        
        # Verify results
        self.assertEqual(len(table_data), 2)
        self.assertEqual(table_data[0]["data"]["ID"], 1)
        self.assertEqual(table_data[0]["data"]["NAME"], "Test1")
        self.assertEqual(table_data[0]["data"]["VALUE"], 100)
        self.assertEqual(table_data[1]["data"]["ID"], 2)
        self.assertEqual(table_data[1]["data"]["NAME"], "Test2")
        self.assertEqual(table_data[1]["data"]["VALUE"], 200)
        
        # Verify method calls
        mock_connect.assert_called_once()
        self.assertEqual(mock_cursor.execute.call_count, 2)
        self.assertEqual(mock_cursor.fetchall.call_count, 2)
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('oracledb.connect')
    def test_execute_query(self, mock_connect):
        """Test execute custom query functionality"""
        # Set up mock objects
        mock_cursor = MagicMock()
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        
        # Set up mock query results
        mock_cursor.description = [("ID",), ("NAME",), ("VALUE",)]
        mock_cursor.fetchall.return_value = [(1, "Test1", 100), (2, "Test2", 200)]
        
        # Call the method being tested
        query_result = self.oracle_service.execute_query("SELECT * FROM TEST_TABLE")
        
        # Verify results
        self.assertEqual(len(query_result), 2)
        self.assertEqual(query_result[0]["ID"], 1)
        self.assertEqual(query_result[0]["NAME"], "Test1")
        self.assertEqual(query_result[0]["VALUE"], 100)
        self.assertEqual(query_result[1]["ID"], 2)
        self.assertEqual(query_result[1]["NAME"], "Test2")
        self.assertEqual(query_result[1]["VALUE"], 200)
        
        # Verify method calls
        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_once_with("SELECT * FROM TEST_TABLE")
        mock_cursor.fetchall.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()
    
    @patch('oracledb.connect')
    def test_connection_error(self, mock_connect):
        """Test database connection error handling"""
        # Set up mock connection to throw exception
        error = oracledb.Error("Connection refused")
        mock_connect.side_effect = error
        
        # Verify exception is properly caught and handled
        with self.assertRaises(Exception) as context:
            self.oracle_service.get_tables()
        
        self.assertIn("Oracle connection error", str(context.exception))

if __name__ == "__main__":
    unittest.main()