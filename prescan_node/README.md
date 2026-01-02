# 🔍 Pre-Scan Node

Automated Infrastructure as Code (IaC) security scanning and remediation node.

## Overview

Pre-Scan Node is a dedicated VM that automatically:
1. **Watches** for new Terraform/Ansible deployment files
2. **Scans** files for security misconfigurations
3. **Fixes** issues automatically using predefined runbooks
4. **Deploys** validated infrastructure

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         Pre-Scan Node                               │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │   Watcher   │───▶│  Scanners   │───▶│  Auto-Fix   │            │
│  │   Service   │    │             │    │   Engine    │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│         │                                     │                    │
│         │                              ┌──────▼──────┐            │
│  ┌──────▼──────┐                       │  Runbooks   │            │
│  │ Deploy Dir  │                       │  Catalog    │            │
│  │ /deploy/in  │                       └─────────────┘            │
│  └─────────────┘                              │                    │
│                                        ┌──────▼──────┐            │
│                                        │  Deployer   │            │
│                                        │  (TF+Ans)   │            │
│                                        └─────────────┘            │
└────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
prescan_node/
├── config/
│   └── prescan_config.yml     # Configuration file
├── runbooks/
│   ├── catalog.yml            # Runbook catalog
│   └── fixes/                 # Fix templates
├── services/
│   ├── watcher.py             # File watcher service
│   ├── scanner.py             # IaC scanner service
│   ├── fixer.py               # Auto-fix service
│   └── deployer.py            # Deployment service
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Quick Start

### 1. Start the Pre-Scan Node

```bash
docker-compose up -d
```

### 2. Drop files for scanning

```bash
# Copy your Terraform/Ansible files to the input directory
cp -r my-terraform-project /deploy/in/
```

### 3. Check results

```bash
# View scan results
curl http://prescan-node:8001/api/scans

# View fix history
curl http://prescan-node:8001/api/fixes
```

## Configuration

Edit `config/prescan_config.yml`:

```yaml
watcher:
  watch_dir: /deploy/in
  poll_interval: 5  # seconds
  
scanners:
  - checkov
  - trivy
  - ansible-lint
  - yamllint

auto_fix:
  enabled: true
  runbook_catalog: /app/runbooks/catalog.yml

deploy:
  enabled: true
  output_dir: /deploy/out
  terraform_apply: true
  ansible_run: true
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/scans` | GET | List all scans |
| `/api/scans/{id}` | GET | Get scan details |
| `/api/fixes` | GET | List all fixes |
| `/api/fixes/{id}` | GET | Get fix details |
| `/api/deploy` | POST | Trigger deployment |
| `/api/status` | GET | System status |
