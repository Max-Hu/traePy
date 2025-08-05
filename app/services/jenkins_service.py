import requests
from typing import List, Dict, Any, Optional
from app.config import settings

class JenkinsService:
    """Jenkins service class providing methods for interacting with Jenkins server"""
    
    def __init__(self):
        """Initialize Jenkins service and set connection parameters"""
        self.jenkins_url = settings.JENKINS_URL
        self.auth = (settings.JENKINS_USER, settings.JENKINS_TOKEN)
        self.headers = {"Content-Type": "application/json"}
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs on Jenkins server"""
        try:
            # Use Jenkins API to get job list
            url = f"{self.jenkins_url}/api/json?tree=jobs[name,url,color]"
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            jobs = []
            
            for job in data.get("jobs", []):
                # Convert Jenkins color attribute to more readable status
                status = "unknown"
                color = job.get("color", "")
                
                if color == "blue":
                    status = "success"
                elif color == "red":
                    status = "failed"
                elif color == "yellow":
                    status = "unstable"
                elif color == "grey":
                    status = "not_built"
                elif "anime" in color:
                    status = "building"
                
                jobs.append({
                    "name": job.get("name", ""),
                    "url": job.get("url", ""),
                    "status": status
                })
            
            return jobs
        except Exception as e:
            raise Exception(f"Failed to get Jenkins jobs: {str(e)}")
    
    def get_job_details(self, job_name: str) -> Dict[str, Any]:
        """Get detailed information of specified job"""
        try:
            url = f"{self.jenkins_url}/job/{job_name}/api/json"
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to get job details: {str(e)}")
    
    def build_job(self, job_name: str, parameters: Optional[Dict[str, Any]] = None) -> int:
        """Trigger Jenkins job build"""
        try:
            # If there are parameters, use parameterized build API
            if parameters:
                url = f"{self.jenkins_url}/job/{job_name}/buildWithParameters"
                response = requests.post(url, auth=self.auth, data=parameters)
            else:
                url = f"{self.jenkins_url}/job/{job_name}/build"
                response = requests.post(url, auth=self.auth)
            
            response.raise_for_status()
            
            # Get queue item ID
            queue_location = response.headers.get("Location")
            if not queue_location:
                raise Exception("Unable to get build queue location")
            
            # Get build number from queue
            queue_id = queue_location.split("/")[-2]
            queue_url = f"{self.jenkins_url}/queue/item/{queue_id}/api/json"
            
            # Poll queue until build number is obtained
            # Note: In real applications, more complex polling strategies or async processing should be used
            import time
            for _ in range(10):  # Try 10 times
                time.sleep(1)  # Wait 1 second
                
                try:
                    queue_response = requests.get(queue_url, auth=self.auth, headers=self.headers)
                    queue_response.raise_for_status()
                    queue_data = queue_response.json()
                    
                    # Check if build number has been assigned
                    executable = queue_data.get("executable")
                    if executable and "number" in executable:
                        return executable["number"]
                except:
                    pass
            
            # If unable to get build number, return -1 indicating triggered but number not obtained
            return -1
        except Exception as e:
            raise Exception(f"Failed to trigger job build: {str(e)}")
    
    def get_build_status(self, job_name: str, build_number: int) -> Dict[str, Any]:
        """Get status of specified build"""
        try:
            url = f"{self.jenkins_url}/job/{job_name}/{build_number}/api/json"
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "job_name": job_name,
                "build_number": build_number,
                "result": data.get("result"),
                "building": data.get("building"),
                "duration": data.get("duration"),
                "timestamp": data.get("timestamp"),
                "url": data.get("url")
            }
        except Exception as e:
            raise Exception(f"Failed to get build status: {str(e)}")