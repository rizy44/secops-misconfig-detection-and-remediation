import os

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4")

# OpenStack API Endpoints to scan
# Format: {"service_name": "endpoint_url"}
OPENSTACK_API_ENDPOINTS = {
    "Cloudformation": "http://192.168.1.229:8000/v1",
    "Compute": "http://192.168.1.229:8774/v2.1",
    "Compute_Legacy": "http://192.168.1.229:8774/v2/450c21c1156b454a9a64934643ab5e1b",
    "Container_Infra": "http://192.168.1.229:9511/v1",
    "Identity": "http://192.168.1.229:5000",
    "Image": "http://192.168.1.229:9292",
    "Network": "http://192.168.1.229:9696",
    "Orchestration": "http://192.168.1.229:8004/v1/450c21c1156b454a9a64934643ab5e1b",
    "Placement": "http://192.168.1.229:8780",
    "Share": "http://192.168.1.229:8786/v1/450c21c1156b454a9a64934643ab5e1b",
    "Sharev2": "http://192.168.1.229:8786/v2",
    "Volumev3": "http://192.168.1.229:8776/v3/450c21c1156b454a9a64934643ab5e1b",
}

# Scanner configuration
API_SCAN_TIMEOUT = int(os.environ.get("API_SCAN_TIMEOUT", "10"))  # seconds
API_SCAN_ENABLED = os.environ.get("API_SCAN_ENABLED", "true").lower() == "true"

# Security checks to perform
SECURITY_CHECKS = {
    "check_auth": True,           # Check authentication requirements
    "check_headers": True,        # Check security headers
    "check_ssl": False,           # Check SSL/TLS (disabled for HTTP endpoints)
    "check_methods": True,        # Check allowed HTTP methods
    "check_version": True,        # Check API version exposure
}

# Expected security headers
EXPECTED_SECURITY_HEADERS = [
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Strict-Transport-Security",  # Only for HTTPS
]

# Dangerous HTTP methods that should not be widely exposed
DANGEROUS_METHODS = ["TRACE", "TRACK", "DELETE", "PUT"]

# Database configuration
DB_PATH = os.environ.get("SECOPS_DB", "/data/secops/findings.db")

# Remediation configuration
ADMIN_CIDR = os.environ.get("ADMIN_CIDR", "192.168.0.0/16")
ANSIBLE_INVENTORY = os.environ.get("ANSIBLE_INVENTORY", "/data/secops/inventory.ini")

# Security scanning configuration
SENSITIVE_PORTS = [
    22,      # SSH
    3389,    # RDP
    3306,    # MySQL
    5432,    # PostgreSQL
    6379,    # Redis
    27017,   # MongoDB
    9200,    # Elasticsearch
    5601,    # Kibana
    15672,   # RabbitMQ Management
    5672,    # RabbitMQ
    10250,   # Kubernetes Kubelet
    6443,    # Kubernetes API
]

# OS baseline scanning
OS_SCAN_ENABLED = os.environ.get("OS_SCAN_ENABLED", "false").lower() == "true"
OS_SCAN_TIMEOUT = int(os.environ.get("OS_SCAN_TIMEOUT", "10"))  # seconds


