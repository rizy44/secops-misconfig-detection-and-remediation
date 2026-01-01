# Security Operations (SecOps) Platform

**A Security Orchestration, Automation, and Response (SOAR) platform for OpenStack**

Automated security scanning, AI-powered remediation suggestions, and self-healing capabilities for OpenStack cloud infrastructure.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenStack](https://img.shields.io/badge/OpenStack-Compatible-red.svg)](https://www.openstack.org/)
[![Terraform](https://img.shields.io/badge/Terraform-%3E%3D1.3-purple.svg)](https://www.terraform.io/)

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## ⚠️ Important: Setup Required

**This repository uses `.example` files for sensitive configurations.**

Before deploying:
1. Copy `.example` files and configure with your values
2. Never commit files with actual credentials
3. See [SETUP.md](SETUP.md) for detailed instructions

Quick setup:
```bash
# Copy configuration files
cp ansible/files/tenantA-openrc.sh.example ansible/files/tenantA-openrc.sh
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# Edit with your actual values
vi ansible/files/tenantA-openrc.sh
vi terraform/terraform.tfvars
```

## 🎯 Overview

SecOps is a comprehensive security automation platform that combines:

- **Automated Security Scanning**: Detect misconfigurations in real-time
- **AI-Powered Remediation**: OpenAI GPT-4 generates remediation suggestions
- **Automated Response**: Execute approved remediations automatically
- **Full Observability**: Prometheus, Grafana, and Loki for monitoring
- **Infrastructure as Code**: Terraform + Ansible for reproducible deployments

### Key Capabilities

✅ **Detection**: Scans OpenStack resources every 5 minutes
✅ **Analysis**: AI-generated remediation suggestions with detailed steps
✅ **Approval Workflow**: Human-in-the-loop for critical actions
✅ **Execution**: Automated remediation via OpenStack SDK and Ansible
✅ **Verification**: Post-remediation validation and status updates
✅ **Monitoring**: Full-stack observability with metrics and logs

## 🌟 Features

### Security Scanning

- **Network Security**: Security groups, floating IPs, port security
- **API Security**: Endpoint authentication, headers, protocols (HTTP/HTTPS)
- **OS Security**: SSH configurations, firewall status, baseline compliance
- **Resource Monitoring**: Instance/volume error states, compliance checks

### Automated Remediation

- Security group rule management (restrict SSH/RDP/DB ports)
- Floating IP management (detach unnecessary exposed IPs)
- Port security enforcement
- SSH hardening (via Ansible)
- Extensible runbook system (YAML-based)

### Intelligence & Reporting

- AI-powered remediation suggestions (OpenAI GPT-4)
- Detailed finding reports with severity classification
- Historical tracking and audit logs
- Prometheus metrics for dashboards
- Loki logs for troubleshooting

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenStack Cloud                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tenant Network: 10.10.50.0/24                       │  │
│  │                                                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │  │
│  │  │  obs_stack   │  │  secops_app  │  │  workload │ │  │
│  │  │  (Gateway)   │  │              │  │           │ │  │
│  │  │              │  │              │  │           │ │  │
│  │  │ • Grafana    │  │ • SecOps API │  │ • Demo    │ │  │
│  │  │ • Prometheus │  │ • Scanner    │  │   Misconfig│ │  │
│  │  │ • Loki       │  │ • Scheduler  │  │           │ │  │
│  │  │ • AlertMgr   │  │              │  │           │ │  │
│  │  │              │  │              │  │           │ │  │
│  │  │ 10.10.50.60  │  │ 10.10.50.163 │  │10.10.50.233│ │  │
│  │  │ FIP:172.10.  │  │              │  │           │ │  │
│  │  │   0.170      │  │              │  │           │ │  │
│  │  └──────────────┘  └──────────────┘  └───────────┘ │  │
│  │         │                  │                │        │  │
│  │         └──────────────────┴────────────────┘        │  │
│  │                        │                              │  │
│  └────────────────────────┼──────────────────────────────┘  │
│                            │                                  │
│  ┌─────────────────────────┴──────────────────────────────┐  │
│  │  Router (Gateway: 10.10.50.1)                         │  │
│  └─────────────────────────┬──────────────────────────────┘  │
│                            │                                  │
└────────────────────────────┼──────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │ External Network│
                    │   (public1)     │
                    └─────────────────┘
```

### Core Components

#### 1. **Gateway VM**
   - Jump host for secure access
   - NAT routing for internal networks
   - Floating IP: Single point of entry

#### 2. **SecOps App VM**
   - FastAPI REST API (port 8000)
   - Security scanners (3 types)
   - Remediation engine with runbooks
   - OpenAI integration for suggestions
   - SQLite database for findings
   - APScheduler (scans every 5 minutes)

#### 3. **Observability Stack VM**
   - Grafana Dashboard (port 3000) - with floating IP
   - Prometheus (port 9090) - metrics storage
   - Loki (port 3100) - log aggregation
   - Alertmanager (port 9093) - alerting

#### 4. **Private VM**
   - Test target for security scans
   - Created from snapshot with pre-configured misconfigurations
   - Isolated in private network

### Technology Stack

**Infrastructure**: Terraform, OpenStack
**Configuration**: Ansible
**Backend**: Python, FastAPI, OpenStack SDK
**AI**: OpenAI GPT-4
**Database**: SQLite
**Monitoring**: Prometheus, Grafana, Loki, Promtail
**Containers**: Docker, Docker Compose

## 📦 Prerequisites

### Required Software

- **Terraform** >= 1.3.0
- **Ansible** >= 2.9  
- **OpenStack CLI** (python-openstackclient)
- **SSH client**
- **Python 3.8+**
- **jq** (for JSON parsing)

### OpenStack Requirements

- OpenStack cloud access with `clouds.yaml` configured
- Ubuntu 22.04 image in Glance
- SSH keypair created
- External network available (e.g., `public1`)
- Required flavors (or adjust in tfvars):
  - `flavor-secops-app` (2 vCPU, 4GB RAM recommended)
  - `flavor-obs-stack` (2 vCPU, 4GB RAM recommended)
  - `flavor-workload` (1 vCPU, 2GB RAM minimum)
- Quota: 4 VMs, 3 volumes (20GB each), 2+ floating IPs

### Optional

- **OpenAI API Key** (for AI-powered suggestions)
- **Domain name** (for production HTTPS access)

## 🚀 Quick Start

### Step 1: Clone and Setup

```bash
git clone <repository-url>
cd project1
```

### Step 2: Configure Credentials

**Important**: Copy example files and configure with your actual values.

```bash
# OpenStack credentials for SecOps App
cp ansible/files/tenantA-openrc.sh.example ansible/files/tenantA-openrc.sh
vi ansible/files/tenantA-openrc.sh  # Add your credentials

# Terraform variables
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
vi terraform/terraform.tfvars  # Configure your settings
```

See [SETUP.md](SETUP.md) for detailed configuration instructions.

### Step 3: Deploy Infrastructure

```bash
cd terraform/

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Deploy
terraform apply
```

### Step 4: Deploy Services

```bash
cd ../ansible/

# Run all playbooks
ansible-playbook -i inventory.ini \
  00-mount-data.yml \
  01-docker.yml \
  02-obs-stack.yml \
  03-agents.yml \
  04-secops-app.yml \
  05-gateway-routing.yml
```

### Step 5: Access

**Grafana Dashboard:**
```bash
# Get floating IP
terraform output obs_stack_floating_ip

# Open browser
http://<floating-ip>:3000
# Login: admin/admin
```

**SecOps CLI:**
```bash
# SSH to container
docker exec -it secops-secops-app-1 bash

# Use CLI
secops-cli findings list
secops-cli scan
```

For detailed setup instructions, see [SETUP.md](SETUP.md).

---

## Old Configuration Format (Deprecated)

### Legacy Bước 2: Cấu hình Terraform (For Reference Only)

The following format is deprecated. Use `.example` files instead:

```hcl
openstack_cloud         = "kolla"           # Tên cloud trong clouds.yaml
name_prefix             = "secops"
image_name              = "Ubuntu-22.04"    # Image trong Glance
keypair_name            = "ecdsa"           # Keypair của bạn
external_network_name   = "public1"         # External network
admin_cidr              = "172.10.0.0/16"   # CIDR của bạn
net_cidr                = "10.10.50.0/24"   # Internal subnet

flavors = {
  secops_app = "flavor-secops-app"
  obs_stack  = "flavor-obs-stack"
  workload   = "flavor-workload"
}

data_volume_sizes = {
  secops_app = 20
  obs_stack  = 20
  workload   = 10
}

enable_fip_obs = true   # Floating IP cho obs_stack
enable_fip_app = false  # Floating IP cho secops_app (optional)
```

### Bước 3: Deploy Infrastructure với Terraform

```bash
cd terraform

# Khởi tạo Terraform
terraform init

# Xem kế hoạch
terraform plan

# Deploy infrastructure
terraform apply

# Lưu ý: Sau khi apply, file inventory.ini sẽ được tạo tự động trong thư mục ansible/
```

### Bước 4: Chuẩn bị Ansible

```bash
cd ../ansible

# Kiểm tra kết nối đến tất cả hosts
ansible all -i inventory.ini -m ping
```

### Bước 5: Deploy Services với Ansible

Chạy các playbooks theo thứ tự:

```bash
# 1. Mount data volumes
ansible-playbook -i inventory.ini 00-mount-data.yml

# 2. Cài đặt Docker
ansible-playbook -i inventory.ini 01-docker.yml

# 3. Deploy observability stack (Prometheus, Loki, Grafana)
ansible-playbook -i inventory.ini 02-obs-stack.yml

# 4. Deploy monitoring agents (Node Exporter, Promtail)
ansible-playbook -i inventory.ini 03-agents.yml

# 5. Deploy SecOps API
ansible-playbook -i inventory.ini 04-secops-app.yml
```

Hoặc chạy tất cả cùng lúc:

```bash
ansible-playbook -i inventory.ini \
  00-mount-data.yml \
  01-docker.yml \
  02-obs-stack.yml \
  03-agents.yml \
  04-secops-app.yml
```

---

## 📖 Usage

### CLI Commands

```bash
# SSH into SecOps App container
docker exec -it secops-secops-app-1 bash

# List findings
secops-cli findings list
secops-cli findings list --severity HIGH
secops-cli findings show <finding-id>

# Trigger scan
secops-cli scan

# AI Suggestions
secops-cli suggestions generate <finding-id>
secops-cli suggestions list
secops-cli suggestions show <suggestion-id>
secops-cli suggestions approve <suggestion-id>

# Remediation
secops-cli remediate run <finding-id>
secops-cli remediate runs
secops-cli remediate show <run-id>

# Statistics
secops-cli stats
```

### REST API

```bash
# From local machine (via SSH tunnel)
ssh -L 8000:10.10.50.237:8000 ubuntu@<gateway-floating-ip>

# In another terminal
curl http://localhost:8000/api/findings
curl http://localhost:8000/api/suggestions
curl -X POST http://localhost:8000/api/scan
```

### Typical Workflow

```bash
# 1. Scan for issues
secops-cli scan

# 2. View findings
secops-cli findings list --severity HIGH

# 3. Generate AI suggestion
secops-cli suggestions generate 1636

# 4. Review suggestion
secops-cli suggestions show 1

# 5. Approve if good
secops-cli suggestions approve 1

# 6. Execute remediation
secops-cli remediate run 1636

# 7. Check result
secops-cli remediate show 1
```

## 📖 Old Usage Section (For Reference)

### Truy cập Grafana Dashboard

1. Lấy Floating IP của obs_stack:
   ```bash
   cd terraform
   terraform output obs_stack_floating_ip
   ```

2. Mở browser:
   ```
   http://<floating_ip>:3000
   ```

3. Đăng nhập:
   - Username: `admin`
   - Password: `admin`

4. Thêm Data Sources:
   - **Prometheus**: URL = `http://prometheus:9090` hoặc `http://localhost:9090`
   - **Loki**: URL = `http://loki:3100` hoặc `http://localhost:3100`

### Xem Findings từ SecOps API

#### Qua API endpoint:

```bash
# Tạo SSH tunnel
ssh -L 8000:10.10.50.163:8000 ubuntu@<obs_stack_floating_ip>

# Hoặc từ gateway
ssh ubuntu@<obs_stack_floating_ip>
curl http://10.10.50.163:8000/findings | python3 -m json.tool
```

#### Qua Prometheus metrics:

Trong Grafana, query:
```
secops_findings_total
rate(secops_findings_total[5m])
```

#### Qua Loki logs:

LogQL query trong Grafana:
```
{job="secops"} |= "FINDING"
```

### Kiểm tra Services

```bash
# Kiểm tra obs_stack services
ansible obs_stack -i ansible/inventory.ini -m shell -a \
  "cd /opt/obs-stack && docker compose ps"

# Kiểm tra secops_app
ansible secops_app -i ansible/inventory.ini -m shell -a \
  "cd /opt/secops/secops_app && docker compose ps"

# Kiểm tra agents
ansible all -i ansible/inventory.ini -m shell -a \
  "cd /opt/agents && docker compose ps"
```

### Xem Logs

```bash
# Logs từ SecOps scanner
ansible secops_app -i ansible/inventory.ini -m shell -a \
  "tail -f /data/secops/secops.log"

# Hoặc qua Loki trong Grafana
# Query: {job="secops"} |= "FINDING"
```

## 🔍 Finding Types

### Network Security (HIGH Severity)
- `SG_WORLD_OPEN_SSH` - SSH (tcp/22) accessible from 0.0.0.0/0
- `SG_WORLD_OPEN_RDP` - RDP (tcp/3389) accessible from 0.0.0.0/0
- `SG_WORLD_OPEN_DB_PORT` - Database ports accessible from 0.0.0.0/0
- `FIP_EXPOSED_INSTANCE` - Instance has floating IP attached
- `PORT_SECURITY_DISABLED` - Neutron port has port security disabled

### API Security (HIGH/MEDIUM)
- `API_INSECURE_PROTOCOL` - API uses HTTP instead of HTTPS
- `API_UNAUTHENTICATED_ACCESS` - API accessible without authentication
- `API_MISSING_SECURITY_HEADERS` - Missing X-Frame-Options, X-Content-Type-Options
- `API_VERSION_DISCLOSURE` - Server headers expose version information
- `API_DANGEROUS_METHODS` - TRACE or TRACK methods allowed

### OS Security (HIGH/MEDIUM)
- `OS_SSH_PASSWORD_AUTH_ENABLED` - SSH password authentication enabled
- `OS_SSH_ROOT_LOGIN_ENABLED` - SSH root login permitted
- `OS_FIREWALL_DISABLED` - UFW or firewalld not running

### Resource Errors (MEDIUM)
- `INSTANCE_ERROR_STATE` - Instance is in ERROR state
- `VOLUME_ERROR_STATE` - Volume has error status

## 🛠️ Troubleshooting

### Lỗi SSH connection refused

```bash
# Kiểm tra security groups
openstack security group rule list secops-sg-ssh-admin

# Kiểm tra instance status
openstack server list

# Kiểm tra floating IP
terraform output obs_stack_floating_ip
```

### Grafana không kết nối được Prometheus/Loki

1. Kiểm tra services đang chạy:
   ```bash
   ssh ubuntu@<obs_stack_floating_ip>
   cd /opt/obs-stack
   docker compose ps
   ```

2. Test từ container:
   ```bash
   docker exec -it <grafana_container> curl http://prometheus:9090/api/v1/status/config
   docker exec -it <grafana_container> curl http://loki:3100/ready
   ```

3. Sửa Data Source URL trong Grafana:
   - Prometheus: `http://prometheus:9090` hoặc `http://localhost:9090`
   - Loki: `http://loki:3100` hoặc `http://localhost:3100`

### SecOps API không scan được

1. Kiểm tra OpenStack credentials:
   ```bash
   ssh ubuntu@10.10.50.163
   cat /opt/secops/secops_app/openstack.env
   ```

2. Kiểm tra logs:
   ```bash
   docker logs secops_api
   # hoặc
   tail -f /data/secops/secops.log
   ```

3. Test kết nối OpenStack:
   ```bash
   ssh ubuntu@10.10.50.163
   source /opt/secops/tenantA-openrc.sh
   openstack server list
   ```

### Prometheus không scrape được targets

1. Kiểm tra Prometheus config:
   ```bash
   ssh ubuntu@<obs_stack_floating_ip>
   cat /opt/obs-stack/prometheus.yml
   ```

2. Kiểm tra targets trong Prometheus UI:
   ```
   http://<obs_stack_floating_ip>:9090/targets
   ```

## 🗑️ Cleanup

Để xóa toàn bộ infrastructure:

```bash
cd terraform
terraform destroy
```

## 📚 Documentation

- [SETUP.md](SETUP.md) - Detailed setup instructions
- [ASSET/SYSTEM_ARCHITECTURE.md](ASSET/SYSTEM_ARCHITECTURE.md) - System architecture details
- [ASSET/ARCHITECTURE_DIAGRAMS.md](ASSET/ARCHITECTURE_DIAGRAMS.md) - Visual diagrams
- [secops_app/DASHBOARD_README.md](secops_app/DASHBOARD_README.md) - Dashboard usage

### External References

- [Terraform OpenStack Provider](https://registry.terraform.io/providers/terraform-provider-openstack/openstack/latest/docs)
- [Ansible Documentation](https://docs.ansible.com/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Loki Documentation](https://grafana.com/docs/loki/latest/)
- [OpenStack SDK](https://docs.openstack.org/openstacksdk/)

## 🔒 Security Considerations

**Important**: This repository is configured to exclude sensitive files via `.gitignore`.

Protected files:
- `*.tfstate` - Terraform state (contains infrastructure details)
- `*.tfvars` - Terraform variables (may contain sensitive configs)
- `*-openrc.sh` - OpenStack credentials
- `*.env` - Environment variables
- `inventory.ini` - Generated inventory with IPs

Always use `.example` files in the repository and configure actual values locally.

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

Please ensure:
- No sensitive data in commits
- Code follows existing style
- Documentation is updated
- Tests pass (if applicable)

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

## 👥 Authors & Acknowledgments

**SecOps Team**

Special thanks to:
- OpenStack community
- Terraform and Ansible communities
- OpenAI for GPT-4 API
- Prometheus, Grafana, and Loki projects

## 📞 Support

For issues and questions:
- Check [SETUP.md](SETUP.md) for common setup issues
- Review [Troubleshooting](#troubleshooting) section
- Open an issue on GitHub
- Check existing issues for similar problems

## 🗺️ Roadmap

Future enhancements:
- [ ] Web dashboard (React/Vue frontend)
- [ ] Multi-cloud support (AWS, Azure)
- [ ] Slack/Teams integration
- [ ] Jira/ServiceNow integration
- [ ] Custom scanner plugins
- [ ] Machine learning for anomaly detection
- [ ] Compliance reporting (CIS, PCI-DSS)
- [ ] Role-based access control (RBAC)

---

**⚠️ Disclaimer**: This is a security automation tool. Always test in non-production environments first. The automated remediation feature should be used with caution and proper approval workflows.








