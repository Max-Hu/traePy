import unittest
from unittest.mock import patch, MagicMock
import requests

from app.services.jenkins_service import JenkinsService

class TestJenkinsService(unittest.TestCase):
    """Unit test class for Jenkins service"""
    
    def setUp(self):
        """Setup work before testing"""
        self.jenkins_service = JenkinsService()
    
    @patch('requests.get')
    def test_get_jobs(self, mock_get):
        """Test getting job list functionality"""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jobs": [
                {"name": "job1", "url": "http://jenkins/job/job1", "color": "blue"},
                {"name": "job2", "url": "http://jenkins/job/job2", "color": "red"},
                {"name": "job3", "url": "http://jenkins/job/job3", "color": "yellow"}
            ]
        }
        mock_get.return_value = mock_response
        
        # Call the method being tested
        jobs = self.jenkins_service.get_jobs()
        
        # Verify results
        self.assertEqual(len(jobs), 3)
        self.assertEqual(jobs[0]["name"], "job1")
        self.assertEqual(jobs[0]["status"], "success")
        self.assertEqual(jobs[1]["name"], "job2")
        self.assertEqual(jobs[1]["status"], "failed")
        self.assertEqual(jobs[2]["name"], "job3")
        self.assertEqual(jobs[2]["status"], "unstable")
        
        # Verify method calls
        mock_get.assert_called_once()
        mock_response.json.assert_called_once()
    
    @patch('requests.get')
    def test_get_job_details(self, mock_get):
        """Test getting job details functionality"""
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "name": "test-job",
            "url": "http://jenkins/job/test-job",
            "description": "Test job description",
            "buildable": True,
            "lastBuild": {"number": 10, "url": "http://jenkins/job/test-job/10/"}
        }
        mock_get.return_value = mock_response
        
        # 调用被测试的方法
        job_details = self.jenkins_service.get_job_details("test-job")
        
        # 验证结果
        self.assertEqual(job_details["name"], "test-job")
        self.assertEqual(job_details["description"], "Test job description")
        self.assertEqual(job_details["lastBuild"]["number"], 10)
        
        # 验证方法调用
        mock_get.assert_called_once()
        mock_response.json.assert_called_once()
    
    @patch('requests.post')
    @patch('requests.get')
    @patch('time.sleep')
    def test_build_job(self, mock_sleep, mock_get, mock_post):
        """Test triggering job build functionality"""
        # Set up mock response - POST request
        mock_post_response = MagicMock()
        mock_post_response.headers = {"Location": "http://jenkins/queue/item/123/"}
        mock_post.return_value = mock_post_response
        
        # Set up mock response - GET request (queue item)
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "executable": {"number": 42, "url": "http://jenkins/job/test-job/42/"}
        }
        mock_get.return_value = mock_get_response
        
        # 调用被测试的方法
        build_number = self.jenkins_service.build_job("test-job")
        
        # 验证结果
        self.assertEqual(build_number, 42)
        
        # 验证方法调用
        mock_post.assert_called_once()
        mock_get.assert_called_once()
        mock_sleep.assert_called_once()
    
    @patch('requests.post')
    def test_build_job_with_parameters(self, mock_post):
        """Test triggering job build with parameters functionality"""
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.headers = {"Location": "http://jenkins/queue/item/123/"}
        mock_post.return_value = mock_response
        
        # Call the method being tested (only testing request part since polling process is hard to mock)
        parameters = {"param1": "value1", "param2": "value2"}
        try:
            self.jenkins_service.build_job("test-job", parameters)
        except Exception:
            # Ignore exceptions caused by incomplete mocking
            pass
        
        # 验证方法调用
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["data"], parameters)
    
    @patch('requests.get')
    def test_get_build_status(self, mock_get):
        """Test getting build status functionality"""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": "SUCCESS",
            "building": False,
            "duration": 12345,
            "timestamp": 1609459200000,
            "url": "http://jenkins/job/test-job/42/"
        }
        mock_get.return_value = mock_response
        
        # Call the method being tested
        build_status = self.jenkins_service.get_build_status("test-job", 42)
        
        # Verify results
        self.assertEqual(build_status["job_name"], "test-job")
        self.assertEqual(build_status["build_number"], 42)
        self.assertEqual(build_status["result"], "SUCCESS")
        self.assertEqual(build_status["building"], False)
        self.assertEqual(build_status["duration"], 12345)
        
        # Verify method calls
        mock_get.assert_called_once()
        mock_response.json.assert_called_once()

if __name__ == "__main__":
    unittest.main()