"""
DataForSEO API Client Service
Simple implementation using requests library
Documentation: https://docs.dataforseo.com/
"""

import logging
import os
import threading
import requests
import base64
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class DataForSEOClient:
    """
    Simple DataForSEO API client using requests
    
    Usage:
        client = get_dataforseo_client()
        result = client.create_keywords_for_site_task('example.com')
    """
    
    BASE_URL = "https://api.dataforseo.com/v3"
    
    def __init__(self):
        """Initialize the DataForSEO client with credentials from environment"""
        self.username = os.getenv('DATA_FOR_SEO_USERNAME')
        self.password = os.getenv('DATA_FOR_SEO_PASSWORD')
        self.webhook_url = os.getenv('DATA_FOR_SEO_HOOK_URL')
        
        if not self.username or not self.password:
            raise ValueError(
                "DataForSEO credentials not found. "
                "Please set DATA_FOR_SEO_USERNAME and DATA_FOR_SEO_PASSWORD environment variables."
            )
        
        # Create auth header
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        
        logger.info(
            f"DataForSEO client initialized for user: {self.username[:3]}***"
            f"{' with webhook URL' if self.webhook_url else ''}"
        )
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Make HTTP request to DataForSEO API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request data
            
        Returns:
            API response as dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            if method == "POST":
                response = requests.post(url, json=data, headers=self.headers, timeout=30)
            elif method == "GET":
                response = requests.get(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"DataForSEO API request failed: {e}")
            raise
    
    def create_keywords_for_site_task(
        self,
        target: str,
        location_code: int = 2840,
        language_code: str = "en",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a Keywords for Site task
        
        Args:
            target: Domain to analyze
            location_code: Location code (default: 2840 for USA)
            language_code: Language code (default: "en")
            **kwargs: Additional parameters
            
        Returns:
            API response with task details
        """
        post_data = [{
            "target": target,
            "location_code": location_code,
            "language_code": language_code,
            **kwargs
        }]
        
        # Don't add webhook URLs - we'll use long polling instead
        
        logger.info(f"Creating Keywords for Site task for: {target}")
        response = self._make_request("POST", "/keywords_data/google_ads/keywords_for_site/task_post", post_data)
        
        return response
    
    def check_tasks_ready(self) -> Dict[str, Any]:
        """
        Check which tasks are ready for download
        
        Returns:
            List of completed task IDs
        """
        endpoint = "/keywords_data/google_ads/keywords_for_site/tasks_ready"
        logger.info("Checking for ready tasks")
        
        response = self._make_request("GET", endpoint)
        return response
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get task result by ID
        
        Args:
            task_id: Task ID from create_keywords_for_site_task
            
        Returns:
            Task result
        """
        endpoint = f"/keywords_data/google_ads/keywords_for_site/task_get/{task_id}"
        logger.info(f"Getting task result for ID: {task_id}")
        
        response = self._make_request("GET", endpoint)
        return response
    
    def check_balance(self) -> Dict[str, Any]:
        """
        Check account balance
        
        Returns:
            Account balance information
        """
        response = self._make_request("GET", "/appendix/user_data")
        return response


# Global instance holder
_client_instance = None
_client_lock = threading.Lock()


def get_dataforseo_client() -> DataForSEOClient:
    """
    Get or create the DataForSEO client instance
    
    Returns:
        DataForSEOClient: The singleton instance
        
    Example:
        from services.dataforseo_client import get_dataforseo_client
        
        client = get_dataforseo_client()
        result = client.create_keywords_for_site_task("example.com")
    """
    global _client_instance
    
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = DataForSEOClient()
    
    return _client_instance


def reset_client():
    """Reset the client instance (useful for testing)"""
    global _client_instance
    with _client_lock:
        _client_instance = None
        logger.info("DataForSEO client instance reset")