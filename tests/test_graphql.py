import unittest
from unittest.mock import patch, MagicMock
import json
import asyncio
from strawberry import Schema
from strawberry.types import ExecutionResult

from app.routes.graphql import schema, Query, Mutation
from app.services.oracle_service import OracleService
from app.services.jenkins_service import JenkinsService

class TestGraphQLQueries(unittest.TestCase):
    """GraphQL查询单元测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.schema = schema
    
    def test_health_query(self):
        """测试健康检查查询"""
        query = """
        query {
            health
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["health"], "Service is healthy")
    
    @patch.object(OracleService, 'get_tables')
    def test_oracle_tables_query(self, mock_get_tables):
        """测试Oracle表列表查询"""
        # 设置模拟返回值
        mock_get_tables.return_value = ["TABLE1", "TABLE2", "TABLE3"]
        
        query = """
        query {
            oracleTables {
                name
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(len(result.data["oracleTables"]), 3)
        self.assertEqual(result.data["oracleTables"][0]["name"], "TABLE1")
        self.assertEqual(result.data["oracleTables"][1]["name"], "TABLE2")
        self.assertEqual(result.data["oracleTables"][2]["name"], "TABLE3")
        
        # 验证服务方法被调用
        mock_get_tables.assert_called_once()
    
    @patch.object(OracleService, 'get_table_data')
    def test_table_data_query(self, mock_get_table_data):
        """测试表数据查询"""
        # 设置模拟返回值
        mock_get_table_data.return_value = [
            {"data": {"ID": 1, "NAME": "Test1", "VALUE": 100}},
            {"data": {"ID": 2, "NAME": "Test2", "VALUE": 200}}
        ]
        
        query = """
        query {
            tableData(tableName: "TEST_TABLE", limit: 2, offset: 0) {
                tableName
                data
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(len(result.data["tableData"]), 2)
        self.assertEqual(result.data["tableData"][0]["tableName"], "TEST_TABLE")
        
        # 验证服务方法被正确参数调用
        mock_get_table_data.assert_called_once_with("TEST_TABLE", 2, 0)
    
    @patch.object(JenkinsService, 'get_jobs')
    def test_jenkins_jobs_query(self, mock_get_jobs):
        """测试Jenkins任务列表查询"""
        # 设置模拟返回值
        mock_get_jobs.return_value = [
            {"name": "job1", "url": "http://jenkins/job/job1", "status": "success"},
            {"name": "job2", "url": "http://jenkins/job/job2", "status": "failed"}
        ]
        
        query = """
        query {
            jenkinsJobs {
                name
                url
                status
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(len(result.data["jenkinsJobs"]), 2)
        self.assertEqual(result.data["jenkinsJobs"][0]["name"], "job1")
        self.assertEqual(result.data["jenkinsJobs"][0]["status"], "success")
        self.assertEqual(result.data["jenkinsJobs"][1]["name"], "job2")
        self.assertEqual(result.data["jenkinsJobs"][1]["status"], "failed")
        
        # 验证服务方法被调用
        mock_get_jobs.assert_called_once()

class TestGraphQLMutations(unittest.TestCase):
    """GraphQL变更操作单元测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.schema = schema
    
    @patch.object(JenkinsService, 'build_job')
    def test_build_job_mutation(self, mock_build_job):
        """测试Jenkins任务构建变更操作"""
        # 设置模拟返回值
        mock_build_job.return_value = 42
        
        mutation = """
        mutation {
            buildJob(input: {jobName: "test-job"}) {
                jobName
                buildNumber
                status
            }
        }
        """
        
        result = self.schema.execute_sync(mutation)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["buildJob"]["jobName"], "test-job")
        self.assertEqual(result.data["buildJob"]["buildNumber"], 42)
        self.assertEqual(result.data["buildJob"]["status"], "triggered")
        
        # 验证服务方法被正确参数调用
        mock_build_job.assert_called_once_with("test-job", None)
    
    @patch.object(JenkinsService, 'build_job')
    def test_build_job_with_parameters_mutation(self, mock_build_job):
        """测试带参数的Jenkins任务构建变更操作"""
        # 设置模拟返回值
        mock_build_job.return_value = 43
        
        # 使用变量传递参数，避免GraphQL语法问题
        mutation = """
        mutation($input: BuildJobInput!) {
            buildJob(input: $input) {
                jobName
                buildNumber
                status
            }
        }
        """
        
        variables = {
            "input": {
                "jobName": "test-job",
                "parameters": {"param1": "value1", "param2": "value2"}
            }
        }
        
        result = self.schema.execute_sync(mutation, variable_values=variables)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["buildJob"]["jobName"], "test-job")
        self.assertEqual(result.data["buildJob"]["buildNumber"], 43)
        self.assertEqual(result.data["buildJob"]["status"], "triggered")
        
        # 验证服务方法被正确参数调用
        expected_params = {"param1": "value1", "param2": "value2"}
        mock_build_job.assert_called_once_with("test-job", expected_params)
    
    @patch.object(JenkinsService, 'build_job')
    def test_build_job_failure_mutation(self, mock_build_job):
        """测试Jenkins任务构建失败的变更操作"""
        # 设置模拟返回值为失败
        mock_build_job.return_value = 0
        
        mutation = """
        mutation {
            buildJob(input: {jobName: "failed-job"}) {
                jobName
                buildNumber
                status
            }
        }
        """
        
        result = self.schema.execute_sync(mutation)
        
        self.assertIsNone(result.errors)
        self.assertIsNotNone(result.data)
        self.assertEqual(result.data["buildJob"]["jobName"], "failed-job")
        self.assertEqual(result.data["buildJob"]["buildNumber"], 0)
        self.assertEqual(result.data["buildJob"]["status"], "failed")
        
        # 验证服务方法被调用
        mock_build_job.assert_called_once_with("failed-job", None)

class TestGraphQLErrorHandling(unittest.TestCase):
    """GraphQL错误处理单元测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.schema = schema
    
    @patch.object(OracleService, 'get_tables')
    def test_oracle_service_error(self, mock_get_tables):
        """测试Oracle服务错误处理"""
        # 设置模拟抛出异常
        mock_get_tables.side_effect = Exception("Oracle连接错误")
        
        query = """
        query {
            oracleTables {
                name
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNotNone(result.errors)
        self.assertIn("Oracle连接错误", str(result.errors))
    
    @patch.object(JenkinsService, 'get_jobs')
    def test_jenkins_service_error(self, mock_get_jobs):
        """测试Jenkins服务错误处理"""
        # 设置模拟抛出异常
        mock_get_jobs.side_effect = Exception("Jenkins连接失败")
        
        query = """
        query {
            jenkinsJobs {
                name
                url
                status
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNotNone(result.errors)
        self.assertIn("Jenkins连接失败", str(result.errors))
    
    def test_invalid_query_syntax(self):
        """测试无效查询语法"""
        invalid_query = """
        query {
            invalidField
        }
        """
        
        result = self.schema.execute_sync(invalid_query)
        
        self.assertIsNotNone(result.errors)
    
    def test_missing_required_parameters(self):
        """测试缺少必需参数"""
        query = """
        query {
            tableData {
                tableName
                data
            }
        }
        """
        
        result = self.schema.execute_sync(query)
        
        self.assertIsNotNone(result.errors)

if __name__ == "__main__":
    unittest.main()