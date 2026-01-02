FROM python:3.11-slim

LABEL maintainer="SecOps Team"
LABEL description="Pre-Scan Node - Automated IaC Security Scanning and Remediation"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    unzip \
    gnupg \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
ARG TERRAFORM_VERSION=1.5.7
RUN curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip -d /usr/local/bin/ \
    && rm terraform.zip \
    && chmod +x /usr/local/bin/terraform

# Install Ansible
RUN pip install --no-cache-dir ansible ansible-lint

# Install IaC scanning tools
RUN pip install --no-cache-dir \
    checkov \
    yamllint

# Create app directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /deploy/in /deploy/out /data/prescan /var/log/prescan

# Environment variables
ENV PRESCAN_CONFIG=/app/config/prescan_config.yml
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose API port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# Run the application
CMD ["python", "main.py"]
