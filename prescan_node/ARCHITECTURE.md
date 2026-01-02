# Pre-Scan Node - Architecture & Usage Guide

## 📋 Overview

Pre-Scan Node là một VM chuyên dụng trong hệ thống SecOps, đảm nhận việc **tự động quét và sửa lỗi** các file IaC (Terraform/Ansible) trước khi deploy.

### 🎯 Mục tiêu

1. **Tự động quét** khi có file deploy mới
2. **Tự động sửa lỗi** theo runbook có sẵn
3. **Hoàn toàn tự động** - không cần can thiệp thủ công
4. **Tích hợp** với SecOps App hiện tại

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OpenStack Cloud                                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     Tenant Network: 10.10.50.0/24                       ││
│  │                                                                          ││
│  │  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐     ││
│  │  │  🔍 Pre-Scan     │   │  🛡️ SecOps App   │   │  🖥️ Workload     │     ││
│  │  │     Node         │   │                  │   │                  │     ││
│  │  │                  │   │                  │   │                  │     ││
│  │  │ • File Watcher   │──▶│ • REST API       │   │                  │     ││
│  │  │ • IaC Scanners   │   │ • Scanners       │   │                  │     ││
│  │  │ • Auto-Fixer     │   │ • Remediation    │   │                  │     ││
│  │  │ • Runbooks       │   │                  │   │                  │     ││
│  │  │ • Ansible/TF     │   │                  │   │                  │     ││
│  │  │                  │   │                  │   │                  │     ││
│  │  │ 📍 10.10.50.100  │   │ 📍 10.10.50.163  │   │ 📍10.10.50.233   │     ││
│  │  │ 🔌 Port: 8001    │   │ 🔌 Port: 8000    │   │                  │     ││
│  │  └──────────────────┘   └──────────────────┘   └──────────────────┘     ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Workflow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Pre-Scan Node Workflow                              │
└────────────────────────────────────────────────────────────────────────────┘

   📁 Git Push / File Drop
          │
          ▼
   ┌─────────────────┐
   │  👀 File Watcher │◄─────────────────────────────────┐
   │    Service       │     Monitors /deploy/in          │
   └────────┬─────────┘                                  │
            │ New TF/Ansible files detected              │
            ▼                                            │
   ┌─────────────────┐                                  │
   │  🔍 IaC Scanners │     Checkov, Trivy,             │
   │                  │     ansible-lint, yamllint       │
   └────────┬─────────┘                                  │
            │                                            │
            ▼                                            │
   ┌─────────────────────────────────────────────┐      │
   │              Findings Detected?              │      │
   └─────────┬──────────────────────┬────────────┘      │
             │ Yes                  │ No                 │
             ▼                      │                    │
   ┌─────────────────┐             │                    │
   │  🔧 Auto-Fixer   │             │                    │
   │   + Runbooks     │             │                    │
   └────────┬─────────┘             │                    │
            │                       │                    │
            ▼                       │                    │
   ┌─────────────────┐             │                    │
   │  ✅ Verification │             │                    │
   │     Re-scan      │─────────────┤                    │
   └────────┬─────────┘             │                    │
            │ Still have issues?    │                    │
            │                       │                    │
   ┌────────┴──────────┐           │                    │
   │ Yes               │ No        │                    │
   ▼                   ▼           ▼                    │
┌─────────┐    ┌─────────────────────────┐             │
│🚨 Alert │    │  🚀 Deploy (TF/Ansible) │             │
│ Manual  │    └───────────┬─────────────┘             │
│ Review  │                │                           │
└─────────┘                ▼                           │
                   ┌─────────────────┐                 │
                   │  📊 Report to   │                 │
                   │   SecOps App    │─────────────────┘
                   └─────────────────┘
```

---

## 📦 Components

### 1. File Watcher Service (`services/watcher.py`)

Theo dõi thư mục `/deploy/in` và phát hiện file mới:

```python
# Patterns được theo dõi
patterns = {
    "terraform": ["*.tf", "*.tfvars"],
    "ansible": ["*.yml", "*.yaml", "playbook*.yml"]
}
```

### 2. IaC Scanner Service (`services/scanner.py`)

Tích hợp nhiều công cụ scan:

| Scanner | Mục đích | Severity |
|---------|----------|----------|
| **Checkov** | Terraform/Ansible security | HIGH, CRITICAL |
| **Trivy** | Container & IaC vulnerabilities | HIGH, CRITICAL |
| **ansible-lint** | Ansible best practices | MEDIUM |
| **yamllint** | YAML formatting | LOW |

### 3. Auto-Fixer Service (`services/fixer.py`)

Tự động sửa lỗi dựa trên runbook catalog:

```yaml
# Ví dụ runbook
tf_sg_restrict_ssh:
  name: "Restrict SSH Access"
  finding_patterns:
    - checkov: "CKV_OPENSTACK_1"
  fix:
    type: regex_replace
    rules:
      - pattern: 'cidr\s*=\s*"0\.0\.0\.0/0".*port\s*=\s*22'
        replacement: 'cidr = "${var.admin_cidr}"'
  severity: HIGH
  auto_approve: false
```

### 4. Deployer Service (`services/deployer.py`)

Thực thi Terraform và Ansible sau khi scan clean:

- Terraform: `init` → `plan` → `apply`
- Ansible: syntax check → run playbook

---

## 🚀 Deployment

### Step 1: Deploy Infrastructure (Terraform)

```bash
cd terraform/
terraform plan
terraform apply
```

### Step 2: Deploy Pre-Scan Node (Ansible)

```bash
cd ansible/
ansible-playbook -i inventory.ini 06-prescan-node.yml
```

### Step 3: Verify

```bash
# Check API health
curl http://10.10.50.100:8001/api/health

# Check status
curl http://10.10.50.100:8001/api/status
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | Node status |
| `/api/scans` | GET | List all scans |
| `/api/scans` | POST | Trigger scan |
| `/api/fixes` | GET | List all fixes |
| `/api/fixes/{id}/rollback` | POST | Rollback fix |
| `/api/deployments` | GET | List deployments |
| `/api/deployments` | POST | Trigger deployment |
| `/api/runbooks` | GET | List runbooks |
| `/api/files` | GET | List watched files |

---

## 📝 Usage Examples

### 1. Drop files for automatic scanning

```bash
# Copy Terraform files to watch directory
scp -r my-terraform-project ubuntu@prescan-node:/deploy/in/

# Pre-Scan Node sẽ tự động:
# 1. Detect new files
# 2. Scan for issues
# 3. Fix issues
# 4. Deploy if clean
```

### 2. Manual scan via API

```bash
# Trigger scan
curl -X POST http://10.10.50.100:8001/api/scans \
  -H "Content-Type: application/json" \
  -d '{"path": "/deploy/in/my-project"}'

# Check results
curl http://10.10.50.100:8001/api/scans
```

### 3. View fix history

```bash
curl http://10.10.50.100:8001/api/fixes
```

### 4. Rollback a fix

```bash
curl -X POST http://10.10.50.100:8001/api/fixes/fix_20260102_123456/rollback
```

---

## ⚙️ Configuration

### Main Configuration (`config/prescan_config.yml`)

```yaml
watcher:
  watch_dir: /deploy/in
  poll_interval: 5  # seconds

scanners:
  enabled:
    - checkov
    - trivy
    - ansible-lint
    - yamllint

auto_fix:
  enabled: true
  runbook_catalog: /app/runbooks/catalog.yml

deploy:
  enabled: true
  terraform:
    auto_apply: false  # Set true for full automation
  ansible:
    enabled: true
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_CIDR` | Admin network CIDR | `10.0.0.0/8` |
| `INTERNAL_CIDR` | Internal network CIDR | `10.10.50.0/24` |
| `SECOPS_API_URL` | SecOps App URL | `http://secops-app:8000` |
| `LOG_LEVEL` | Logging level | `INFO` |

---

## 🔐 Runbook Catalog

### Available Runbooks

| Runbook ID | Finding Type | Auto-Approve |
|------------|--------------|--------------|
| `tf_sg_restrict_ssh` | SSH open to world | ❌ |
| `tf_sg_restrict_rdp` | RDP open to world | ❌ |
| `tf_sg_restrict_db` | DB ports open | ❌ |
| `tf_add_required_tags` | Missing tags | ✅ |
| `ansible_fix_ssh_config` | SSH config issues | ❌ |
| `ansible_fix_file_permissions` | Missing mode | ✅ |
| `yaml_fix_formatting` | YAML formatting | ✅ |
| `tf_enable_port_security` | Port security disabled | ❌ |

### Adding Custom Runbooks

Edit `runbooks/catalog.yml`:

```yaml
my_custom_fix:
  name: "My Custom Fix"
  description: "Fix specific issue"
  finding_patterns:
    - checkov: "CKV_CUSTOM_123"
  fix:
    type: regex_replace
    target_files:
      - "*.tf"
    rules:
      - pattern: 'bad_config'
        replacement: 'good_config'
  severity: HIGH
  auto_approve: false
```

---

## 🔗 Integration with SecOps App

Pre-Scan Node tự động sync findings với SecOps App:

```yaml
secops_integration:
  enabled: true
  secops_api_url: "http://secops-app:8000"
  sync_findings: true
  sync_interval: 60  # seconds
```

Findings từ Pre-Scan Node sẽ xuất hiện trong SecOps App dashboard.

---

## 📊 Monitoring

### Logs

```bash
# View container logs
docker logs -f prescan-node

# View application logs
tail -f /var/log/prescan/prescan.log
```

### Metrics (Prometheus)

Pre-Scan Node exports metrics tại `/metrics` (port 8001).

---

## 🛠️ Troubleshooting

### Container not starting

```bash
# Check logs
docker logs prescan-node

# Check container status
docker ps -a | grep prescan
```

### Scanner not detecting files

```bash
# Check watch directory
ls -la /deploy/in/

# Check watcher status
curl http://localhost:8001/api/status
```

### Fix not applied

```bash
# Check fix history
curl http://localhost:8001/api/fixes

# Check runbook catalog
cat /app/runbooks/catalog.yml
```

---

## 📁 File Structure

```
prescan_node/
├── config/
│   └── prescan_config.yml     # Main configuration
├── runbooks/
│   └── catalog.yml            # Fix runbooks
├── services/
│   ├── __init__.py
│   ├── watcher.py             # File watcher
│   ├── scanner.py             # IaC scanners
│   ├── fixer.py               # Auto-fix engine
│   └── deployer.py            # Deployment service
├── main.py                    # Application entry
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🎛️ Full Automation Mode

Để bật chế độ tự động hoàn toàn (không cần approval):

```yaml
# config/prescan_config.yml
auto_fix:
  enabled: true
  auto_approve:
    - security_group_changes    # Thêm vào đây
    - network_changes
    - yaml_formatting
    - missing_tags

deploy:
  terraform:
    auto_apply: true            # Enable auto-apply
  ansible:
    enabled: true
```

⚠️ **Cảnh báo**: Chỉ sử dụng ở môi trường non-production!
