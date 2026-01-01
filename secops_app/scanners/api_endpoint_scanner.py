"""
API Endpoint Scanner Module
Scans OpenStack API endpoints for misconfigurations and security issues.
"""

import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime

log = logging.getLogger("secops")


class APIEndpointScanner:
    """Scanner for OpenStack API endpoints"""
    
    def __init__(self, endpoints: Dict[str, str], timeout: int = 10):
        """
        Initialize scanner
        
        Args:
            endpoints: Dict of service_name: endpoint_url
            timeout: Request timeout in seconds
        """
        self.endpoints = endpoints
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, verify=False)  # verify=False for self-signed certs
    
    def scan_all(self) -> List[Dict]:
        """
        Scan all configured endpoints
        
        Returns:
            List of findings
        """
        findings = []
        
        for service_name, endpoint_url in self.endpoints.items():
            try:
                service_findings = self.scan_endpoint(service_name, endpoint_url)
                findings.extend(service_findings)
            except Exception as e:
                log.error(f"Error scanning {service_name} ({endpoint_url}): {e}")
                # Report scan failure as finding
                findings.append({
                    "type": "API_SCAN_ERROR",
                    "severity": "LOW",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"Failed to scan {service_name}: {str(e)}"
                })
        
        return findings
    
    def scan_endpoint(self, service_name: str, endpoint_url: str) -> List[Dict]:
        """
        Scan a single endpoint for misconfigurations
        
        Args:
            service_name: Name of the service
            endpoint_url: URL of the endpoint
            
        Returns:
            List of findings for this endpoint
        """
        findings = []
        
        try:
            # Try to access the endpoint
            response = self.client.get(endpoint_url, follow_redirects=True)
            
            # Check 1: Unauthenticated access to sensitive endpoints
            if response.status_code == 200:
                findings.append({
                    "type": "API_UNAUTHENTICATED_ACCESS",
                    "severity": "HIGH",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"{service_name} API accessible without authentication (HTTP {response.status_code})"
                })
            
            # Check 2: Missing security headers
            missing_headers = self._check_security_headers(response)
            if missing_headers:
                findings.append({
                    "type": "API_MISSING_SECURITY_HEADERS",
                    "severity": "MEDIUM",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"{service_name} missing security headers: {', '.join(missing_headers)}"
                })
            
            # Check 3: Version information disclosure
            if self._check_version_disclosure(response):
                findings.append({
                    "type": "API_VERSION_DISCLOSURE",
                    "severity": "LOW",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"{service_name} exposes version information in headers"
                })
            
            # Check 4: Dangerous HTTP methods allowed
            dangerous_methods = self._check_http_methods(endpoint_url)
            if dangerous_methods:
                findings.append({
                    "type": "API_DANGEROUS_METHODS",
                    "severity": "MEDIUM",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"{service_name} allows dangerous methods: {', '.join(dangerous_methods)}"
                })
            
            # Check 5: HTTP instead of HTTPS
            if endpoint_url.startswith("http://") and not endpoint_url.startswith("http://127.0.0.1") and not endpoint_url.startswith("http://localhost"):
                findings.append({
                    "type": "API_INSECURE_PROTOCOL",
                    "severity": "HIGH",
                    "service_name": service_name,
                    "endpoint_url": endpoint_url,
                    "resource_id": endpoint_url,
                    "summary": f"{service_name} uses insecure HTTP protocol instead of HTTPS"
                })
                
        except httpx.ConnectError:
            log.debug(f"{service_name} ({endpoint_url}) is not accessible (connection refused)")
        except httpx.TimeoutException:
            findings.append({
                "type": "API_TIMEOUT",
                "severity": "LOW",
                "service_name": service_name,
                "endpoint_url": endpoint_url,
                "resource_id": endpoint_url,
                "summary": f"{service_name} request timed out after {self.timeout}s"
            })
        except Exception as e:
            log.error(f"Unexpected error scanning {service_name}: {e}")
        
        return findings
    
    def _check_security_headers(self, response: httpx.Response) -> List[str]:
        """
        Check for missing security headers
        
        Returns:
            List of missing header names
        """
        missing = []
        important_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
        ]
        
        for header in important_headers:
            if header.lower() not in [h.lower() for h in response.headers.keys()]:
                missing.append(header)
        
        return missing
    
    def _check_version_disclosure(self, response: httpx.Response) -> bool:
        """
        Check if version information is disclosed in headers
        
        Returns:
            True if version info found
        """
        version_headers = ["Server", "X-Powered-By", "X-OpenStack-Nova-API-Version"]
        
        for header in version_headers:
            if header in response.headers:
                value = response.headers[header]
                # Check if value contains version numbers
                if any(char.isdigit() for char in value):
                    return True
        
        return False
    
    def _check_http_methods(self, endpoint_url: str) -> List[str]:
        """
        Check for dangerous HTTP methods
        
        Returns:
            List of dangerous methods that are allowed
        """
        dangerous = []
        dangerous_methods = ["TRACE", "TRACK"]
        
        try:
            # Send OPTIONS request to check allowed methods
            response = self.client.request("OPTIONS", endpoint_url)
            
            if "Allow" in response.headers:
                allowed = [m.strip().upper() for m in response.headers["Allow"].split(",")]
                dangerous = [m for m in dangerous_methods if m in allowed]
        except Exception as e:
            log.debug(f"Could not check HTTP methods for {endpoint_url}: {e}")
        
        return dangerous
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()




