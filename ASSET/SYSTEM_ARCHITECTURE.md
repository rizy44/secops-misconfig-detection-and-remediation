# Hệ thống Giám sát và Quét Bảo mật Tự động - Mô tả Chi tiết

## 1. Tổng quan Hệ thống

### 1.1. Mục đích

Hệ thống được thiết kế để tự động phát hiện và giám sát các misconfigurations bảo mật trong môi trường OpenStack, tích hợp với observability stack để thu thập, lưu trữ và hiển thị metrics, logs và findings.

### 1.2. Các tính năng chính

- **Infrastructure as Code**: Tự động hóa việc tạo và quản lý infrastructure trên OpenStack
- **Tự động quét bảo mật**: 
  - Scanner quét OpenStack resources (Security Groups, Servers, Volumes)
  - API Endpoint Scanner quét 12 OpenStack API endpoints
- **AI-Powered Suggestions**: Tích hợp OpenAI để tự động tạo remediation suggestions
- **Web Dashboard**: Giao diện web để xem findings, filter, và quản lý suggestions
- **Observability**: Thu thập metrics và logs từ tất cả components
- **Visualization**: Dashboard Grafana để hiển thị findings và metrics
- **Centralized Logging**: Loki để tập trung logs từ tất cả services

## 2. Kiến trúc Hệ thống

### 2.1. Sơ đồ Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                         User/Admin                              │
│                    (172.10.0.0/16)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ HTTPS/SSH
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    OpenStack Cloud                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  External Network (public1)                              │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  Router (Gateway: 10.10.50.1)                     │  │   │
│  │  │  ┌──────────────────────────────────────────────┐ │  │   │
│  │  │  │  Tenant Network: 10.10.50.0/24              │ │  │   │
│  │  │  │                                               │ │  │   │
│  │  │  │  ┌──────────────┐  ┌──────────────┐         │ │  │   │
│  │  │  │  │  obs_stack  │  │  secops_app  │         │ │  │   │
│  │  │  │  │  (Gateway)  │  │              │         │ │  │   │
│  │  │  │  │              │  │              │         │ │  │   │
│  │  │  │  │ • Grafana    │  │ • SecOps API │         │ │  │   │
│  │  │  │  │ • Prometheus │  │ • Scanner    │         │ │  │   │
│  │  │  │  │ • Loki       │  │ • Scheduler │         │ │  │   │
│  │  │  │  │ • AlertMgr   │  │ • Database  │         │ │  │   │
│  │  │  │  │              │  │              │         │ │  │   │
│  │  │  │  │ 10.10.50.60  │  │ 10.10.50.163 │         │ │  │   │
│  │  │  │  │ FIP:172.10.  │  │              │         │ │  │   │
│  │  │  │  │   0.170      │  │              │         │ │  │   │
│  │  │  │  └──────┬───────┘  └──────┬───────┘         │ │  │   │
│  │  │  │         │                 │                 │ │  │   │
│  │  │  │         └─────────┬───────┘                 │ │  │   │
│  │  │  │                   │                         │ │  │   │
│  │  │  │         ┌──────────▼──────────┐             │ │  │   │
│  │  │  │         │    workload         │             │ │  │   │
│  │  │  │         │  (Demo Misconfig)   │             │ │  │   │
│  │  │  │         │  10.10.50.233       │             │ │  │   │
│  │  │  │         └─────────────────────┘             │ │  │   │
│  │  │  └──────────────────────────────────────────────┘ │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2. Luồng Dữ liệu (Data Flow)

```
┌─────────────┐
│  OpenStack  │
│  Resources  │
└──────┬──────┘
       │
       │ Scan (mỗi 60s)
       │
┌──────▼──────────────────────────────────────┐
│         SecOps API (secops_app)             │
│  ┌──────────────────────────────────────┐  │
│  │  OpenStack Resource Scanner:         │  │
│  │  • scan_security_groups()            │  │
│  │  • scan_servers()                    │  │
│  │  • scan_volumes()                   │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  API Endpoint Scanner:               │  │
│  │  • Quét 12 OpenStack API endpoints  │  │
│  │  • Phát hiện unauthenticated access │  │
│  │  • Kiểm tra security headers        │  │
│  │  • Phát hiện version disclosure     │  │
│  │  • Kiểm tra HTTP methods            │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  OpenAI Service:                     │  │
│  │  • Generate remediation suggestions │  │
│  │  • AI-powered security advice       │  │
│  └──────────────────────────────────────┘  │
│              │                              │
│              │ Findings                     │
│              │                              │
│  ┌───────────▼───────────┐                 │
│  │  SQLite Database      │                 │
│  │  (findings.db)        │                 │
│  └───────────┬───────────┘                 │
│              │                              │
│              │                              │
│  ┌───────────▼───────────┐                 │
│  │  Prometheus Metrics   │                 │
│  │  • secops_findings_   │                 │
│  │    total              │                 │
│  │  • secops_scan_       │                 │
│  │    duration_seconds   │                 │
│  └───────────┬───────────┘                 │
│              │                              │
│  ┌───────────▼───────────┐                 │
│  │  Logs (secops.log)    │                 │
│  └───────────┬───────────┘                 │
└──────────────┼──────────────────────────────┘
               │
               │ Metrics (port 8000/metrics)
               │ Logs (via Promtail)
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────────┐    ┌───────▼────────┐
│ Prometheus │    │      Loki      │
│  (9090)    │    │     (3100)      │
└─────┬──────┘    └───────┬─────────┘
      │                   │
      └──────────┬─────────┘
                 │
        ┌────────▼────────┐
        │     Grafana     │
        │     (3000)      │
        │                 │
        │  • Dashboards   │
        │  • Alerts       │
        │  • Logs View    │
        └─────────────────┘
```

### 2.3. Kiến trúc Network

```
External Network (public1)
    │
    │ Floating IP: 172.10.0.170
    │
    ▼
┌─────────────────┐
│  Router Gateway │
│  10.10.50.1     │
└────────┬────────┘
         │
         │ Tenant Network: 10.10.50.0/24
         │
    ┌────┴────┬──────────────┐
    │         │              │
┌───▼───┐ ┌──▼────┐    ┌────▼────┐
│obs_   │ │secops │    │ workload │
│stack  │ │_app   │    │          │
│       │ │       │    │          │
│10.10. │ │10.10. │    │10.10.    │
│50.60  │ │50.163 │    │50.233    │
└───────┘ └───────┘    └──────────┘
```

### 2.4. Security Groups

#### obs_stack (Gateway)
- **sg_ssh_admin**: SSH từ admin_cidr (172.10.0.0/16) và subnet (10.10.50.0/24)
- **sg_obs_public**: Grafana (3000) từ admin_cidr và subnet
- **sg_internal**: Internal ports (Prometheus 9090, Loki 3100, Node Exporter 9100)

#### secops_app
- **sg_ssh_admin**: SSH từ admin_cidr và subnet
- **sg_internal**: Internal ports (SecOps API 8000)

#### workload
- **sg_ssh_admin**: SSH từ admin_cidr và subnet
- **sg_demo_misconfig**: SSH mở cho 0.0.0.0/0 (để demo scanner phát hiện)

## 3. Các Thành phần Hệ thống

### 3.1. Infrastructure Layer (Terraform)

#### 3.1.1. Network Components
- **Network**: `secops-net` (10.10.50.0/24)
- **Subnet**: `secops-subnet` với DNS servers (8.8.8.8, 1.1.1.1)
- **Router**: `secops-router` kết nối với external network
- **Router Interface**: Kết nối subnet với router

#### 3.1.2. Compute Resources
- **obs_stack**: 
  - Flavor: `flavor-obs-stack`
  - Volume: 20GB
  - Floating IP: Có (172.10.0.170)
  - Role: Gateway và Observability Stack
  
- **secops_app**:
  - Flavor: `flavor-secops-app`
  - Volume: 20GB
  - Floating IP: Không (truy cập qua gateway)
  - Role: SecOps Scanner API
  
- **workload**:
  - Flavor: `flavor-workload`
  - Volume: 10GB
  - Floating IP: Không
  - Role: Demo misconfiguration

#### 3.1.3. Storage
- Mỗi instance có 1 Cinder volume (`/dev/vdb`) được mount vào `/data`
- Volumes được format ext4 và mount tự động

### 3.2. Configuration Layer (Ansible)

#### 3.2.1. Playbook 00-mount-data.yml
- Mount data volumes (`/dev/vdb` → `/data`)
- Format filesystem nếu cần
- Tạo mount point và cấu hình fstab

#### 3.2.2. Playbook 01-docker.yml
- Cài đặt Docker và Docker Compose v2
- Thêm user ubuntu vào docker group
- Verify installation

#### 3.2.3. Playbook 02-obs-stack.yml
Deploy observability stack trên obs_stack:
- **Prometheus**: Metrics collection và storage
- **Loki**: Log aggregation
- **Grafana**: Visualization và dashboards
- **Alertmanager**: Alert management

Cấu hình:
- Prometheus scrape config từ inventory (node exporters, secops API)
- Loki config với filesystem storage
- Grafana với admin password

#### 3.2.4. Playbook 03-agents.yml
Deploy monitoring agents trên tất cả hosts:
- **Node Exporter**: System metrics (CPU, memory, disk, network)
- **Promtail**: Log collection và gửi đến Loki

Cấu hình:
- Promtail config với Loki push URL từ inventory
- Scrape configs cho: syslog, auth.log, nginx logs, secops.log

#### 3.2.5. Playbook 04-secops-app.yml
Deploy SecOps API trên secops_app:
- Copy source code từ `secops_app/`
- Generate OpenStack credentials từ OpenRC file
- Start FastAPI container với Docker Compose

### 3.3. Application Layer

#### 3.3.1. SecOps Scanner API

**Technology Stack:**
- FastAPI: Web framework
- APScheduler: Background job scheduler
- OpenStack SDK: OpenStack API client
- Prometheus Client: Metrics export
- SQLite: Findings storage

**Components:**

1. **OpenStack Resource Scanner:**
   ```python
   - scan_security_groups(): Phát hiện SG mở SSH to world
   - scan_servers(): Phát hiện servers có status ERROR
   - scan_volumes(): Phát hiện volumes có status lỗi
   ```

2. **API Endpoint Scanner:**
   ```python
   - APIEndpointScanner: Quét 12 OpenStack API endpoints
   - Phát hiện: unauthenticated access, missing headers, 
     version disclosure, dangerous methods, insecure protocol
   - Services: Compute, Network, Identity, Image, Volume, etc.
   ```

3. **OpenAI Integration:**
   ```python
   - OpenAIService: Generate remediation suggestions
   - AI-powered security recommendations
   - Supports approval workflow
   ```

4. **Scheduler:**
   - Chạy mỗi 60 giây (configurable via SCAN_INTERVAL_SEC)
   - Sử dụng APScheduler BackgroundScheduler
   - Max 1 instance tại một thời điểm

5. **Data Storage:**
   - SQLite database: `/data/secops/findings.db`
   - Tables:
     - `findings(id, ts, ftype, severity, resource_id, summary, service_name, endpoint_url, status)`
     - `suggestions(id, finding_id, suggestion_text, status, created_at, updated_at)`
     - `api_endpoints(id, service_name, endpoint_url, last_scanned, status)`

6. **API Endpoints:**
   - `GET /`: Web Dashboard (HTML)
   - `GET /metrics`: Prometheus metrics
   - `GET /api/findings`: List findings (với filters: service, severity, status)
   - `GET /api/services`: List OpenStack services với findings count
   - `POST /api/scan`: Trigger manual scan
   - `POST /api/suggestions/{finding_id}`: Generate AI suggestion
   - `GET /api/suggestions`: List suggestions
   - `POST /api/suggestions/{id}/approve`: Approve suggestion
   - `POST /api/suggestions/{id}/reject`: Reject suggestion
   - `GET /findings`: Legacy endpoint (backward compatibility)

7. **Metrics:**
   - `secops_findings_total{type, severity}`: Counter
   - `secops_scan_duration_seconds`: Histogram

8. **Web Dashboard:**
   - Frontend: HTML/CSS/JavaScript (static files)
   - Served tại root path: `GET /`
   - Features:
     - Statistics cards (Total Findings, High Severity, Pending Suggestions, Services Scanned)
     - Filterable findings table (by service, severity, status)
     - AI suggestion generation với một click
     - Approval/rejection workflow
     - Real-time updates

9. **Logging:**
   - File: `/data/secops/secops.log`
   - Format: `%(asctime)s %(levelname)s %(message)s`
   - Findings được log với level WARNING

#### 3.3.2. Observability Stack

**Prometheus:**
- Port: 9090
- Storage: `/data/prometheus`
- Retention: 3 days
- Scrape interval: 15s
- Targets:
  - Node Exporters (tất cả hosts:9100)
  - SecOps API (secops_app:8000)

**Loki:**
- Port: 3100
- Storage: `/data/loki`
- Retention: 72h
- Schema: v13 (TSDB)
- Receives logs từ Promtail

**Grafana:**
- Port: 3000
- Storage: `/data/grafana`
- Default credentials: admin/admin
- Data Sources:
  - Prometheus: `http://prometheus:9090`
  - Loki: `http://loki:3100`

**Alertmanager:**
- Port: 9093
- Storage: `/data/alertmanager`
- Config: Basic route và receiver

## 4. Quy trình Hoạt động

### 4.1. Deployment Flow

```
1. Terraform Apply
   ├── Create Network, Subnet, Router
   ├── Create Security Groups
   ├── Create Ports với Fixed IPs
   ├── Create Instances
   ├── Create Volumes và Attach
   ├── Create Floating IPs
   └── Generate Ansible Inventory

2. Ansible Playbooks (theo thứ tự)
   ├── 00-mount-data.yml: Mount volumes
   ├── 01-docker.yml: Install Docker
   ├── 02-obs-stack.yml: Deploy observability
   ├── 03-agents.yml: Deploy agents
   └── 04-secops-app.yml: Deploy scanner

3. Services Start
   ├── Docker containers start
   ├── Prometheus scrape targets
   ├── Promtail collect logs
   └── SecOps scanner start schedule
```

### 4.2. Scanning Flow

```
1. Scheduler Trigger (mỗi 60s)
   │
   ▼
2. run_scan() được gọi
   │
   ├── get_conn() → OpenStack connection
   │
   ├── OpenStack Resource Scans
   │   ├── scan_security_groups()
   │   │   └── Check SG rules: SSH open to 0.0.0.0/0
   │   ├── scan_servers()
   │   │   └── Check server status: ERROR
   │   └── scan_volumes()
   │       └── Check volume status: error_*
   │
   └── API Endpoint Scans (nếu enabled)
       └── APIEndpointScanner.scan_all()
           └── Quét 12 OpenStack API endpoints
               ├── Check authentication
               ├── Check security headers
               ├── Check version disclosure
               ├── Check HTTP methods
               └── Check protocol (HTTP vs HTTPS)
   │
   ▼
3. Findings Processing
   │
   ├── Update Prometheus metrics
   │   └── secops_findings_total.inc()
   │
   ├── Insert vào SQLite DB
   │   └── db_insert(findings)
   │
   └── Log findings
       └── log.warning("FINDING ...")
   │
   ▼
4. Data Flow
   │
   ├── Metrics → Prometheus (scrape /metrics)
   ├── Logs → Promtail → Loki
   └── Database → API endpoint (/findings)
```

### 4.3. Monitoring Flow

```
1. Metrics Collection
   │
   ├── Node Exporter (mỗi host)
   │   └── System metrics → Prometheus
   │
   └── SecOps API
       └── Application metrics → Prometheus

2. Logs Collection
   │
   ├── Promtail (mỗi host)
   │   ├── /var/log/syslog
   │   ├── /var/log/auth.log
   │   ├── /var/log/nginx/*.log
   │   └── /data/secops/secops.log
   │
   └── Push to Loki

3. Visualization
   │
   └── Grafana
       ├── Query Prometheus (metrics)
       ├── Query Loki (logs)
       └── Display dashboards
```

## 5. Các Loại Findings

### 5.1. OpenStack Resource Findings

#### SG_OPEN_SSH (HIGH)

**Mô tả:** Security Group cho phép SSH từ 0.0.0.0/0

**Điều kiện phát hiện:**
- `remote_ip_prefix == "0.0.0.0/0"`
- `protocol == "tcp"`
- `port_range_min == 22 && port_range_max == 22`

**Ví dụ:**
```json
{
  "type": "SG_OPEN_SSH",
  "severity": "HIGH",
  "resource_id": "sg-xxx",
  "summary": "SecurityGroup secops-sg-demo-misconfig allows 0.0.0.0/0 tcp/22"
}
```

**Demo:** workload instance có security group này

#### NOVA_SERVER_ERROR (MEDIUM)

**Mô tả:** Server có status = ERROR

**Điều kiện phát hiện:**
- `server.status.upper() == "ERROR"`

**Ví dụ:**
```json
{
  "type": "NOVA_SERVER_ERROR",
  "severity": "MEDIUM",
  "resource_id": "server-xxx",
  "summary": "Server secops-workload status=ERROR"
}
```

#### CINDER_VOLUME_ERROR (MEDIUM)

**Mô tả:** Volume có status lỗi

**Điều kiện phát hiện:**
- `volume.status.lower() in ("error", "error_restoring", "error_extending", "error_deleting")`

**Ví dụ:**
```json
{
  "type": "CINDER_VOLUME_ERROR",
  "severity": "MEDIUM",
  "resource_id": "volume-xxx",
  "summary": "Volume secops-vol-workload-data status=error"
}
```

### 5.2. API Endpoint Findings

#### API_UNAUTHENTICATED_ACCESS (HIGH)

**Mô tả:** API endpoint có thể truy cập mà không cần authentication

**Điều kiện phát hiện:**
- HTTP status code = 200 khi không có token
- Endpoint trả về data thay vì 401/403

**Ví dụ:**
```json
{
  "type": "API_UNAUTHENTICATED_ACCESS",
  "severity": "HIGH",
  "service_name": "Compute",
  "endpoint_url": "http://192.168.1.229:8774/v2.1",
  "summary": "Compute API accessible without authentication (HTTP 200)"
}
```

#### API_INSECURE_PROTOCOL (HIGH)

**Mô tả:** API endpoint sử dụng HTTP thay vì HTTPS

**Điều kiện phát hiện:**
- Endpoint URL bắt đầu với `http://` (không phải localhost)

**Ví dụ:**
```json
{
  "type": "API_INSECURE_PROTOCOL",
  "severity": "HIGH",
  "service_name": "Identity",
  "endpoint_url": "http://192.168.1.229:5000",
  "summary": "Identity uses insecure HTTP protocol instead of HTTPS"
}
```

#### API_MISSING_SECURITY_HEADERS (MEDIUM)

**Mô tả:** API endpoint thiếu security headers

**Điều kiện phát hiện:**
- Missing `X-Content-Type-Options`
- Missing `X-Frame-Options`

**Ví dụ:**
```json
{
  "type": "API_MISSING_SECURITY_HEADERS",
  "severity": "MEDIUM",
  "service_name": "Network",
  "endpoint_url": "http://192.168.1.229:9696",
  "summary": "Network missing security headers: X-Content-Type-Options, X-Frame-Options"
}
```

#### API_DANGEROUS_METHODS (MEDIUM)

**Mô tả:** API endpoint cho phép dangerous HTTP methods

**Điều kiện phát hiện:**
- OPTIONS request trả về `Allow` header chứa TRACE hoặc TRACK

**Ví dụ:**
```json
{
  "type": "API_DANGEROUS_METHODS",
  "severity": "MEDIUM",
  "service_name": "Image",
  "endpoint_url": "http://192.168.1.229:9292",
  "summary": "Image allows dangerous methods: TRACE, TRACK"
}
```

#### API_VERSION_DISCLOSURE (LOW)

**Mô tả:** API endpoint expose version information trong headers

**Điều kiện phát hiện:**
- Headers chứa: `Server`, `X-Powered-By`, `X-OpenStack-Nova-API-Version`
- Value chứa số version

**Ví dụ:**
```json
{
  "type": "API_VERSION_DISCLOSURE",
  "severity": "LOW",
  "service_name": "Compute",
  "endpoint_url": "http://192.168.1.229:8774/v2.1",
  "summary": "Compute exposes version information in headers"
}
```

#### API_TIMEOUT (LOW)

**Mô tả:** API endpoint không response trong timeout period

**Điều kiện phát hiện:**
- Request timeout sau 10 giây (configurable)

**Ví dụ:**
```json
{
  "type": "API_TIMEOUT",
  "severity": "LOW",
  "service_name": "Placement",
  "endpoint_url": "http://192.168.1.229:8780",
  "summary": "Placement request timed out after 10s"
}
```

#### API_SCAN_ERROR (LOW)

**Mô tả:** Lỗi khi scan API endpoint

**Điều kiện phát hiện:**
- Exception xảy ra khi scan endpoint

**Ví dụ:**
```json
{
  "type": "API_SCAN_ERROR",
  "severity": "LOW",
  "service_name": "Cloudformation",
  "endpoint_url": "http://192.168.1.229:8000/v1",
  "summary": "Failed to scan Cloudformation: Connection refused"
}
```

## 6. Cấu hình và Tùy chỉnh

### 6.1. Scan Interval

Thay đổi trong `ansible/04-secops-app.yml` hoặc environment variable:

```yaml
environment:
  - SCAN_INTERVAL_SEC=120  # 2 phút thay vì 60 giây
```

### 6.2. Prometheus Retention

Trong `ansible/templates/docker-compose.yml.j2`:

```yaml
command:
  - "--storage.tsdb.retention.time=7d"  # 7 ngày
```

### 6.3. Loki Retention

Trong `ansible/templates/loki-config.yml`:

```yaml
limits_config:
  retention_period: 168h  # 7 ngày
```

### 6.4. Thêm Scanner Rules

#### Thêm OpenStack Resource Scanner

Trong `secops_app/app.py`, thêm function mới:

```python
def scan_new_resource(conn):
    findings = []
    # Logic scan
    return findings

# Thêm vào run_scan():
all_findings += scan_new_resource(conn)
```

#### Thêm API Endpoint Scanner Rules

Trong `secops_app/scanners/api_endpoint_scanner.py`, thêm check mới trong `scan_endpoint()`:

```python
def scan_endpoint(self, service_name: str, endpoint_url: str) -> List[Dict]:
    findings = []
    # ... existing checks ...
    
    # New check
    if self._check_new_security_issue(response):
        findings.append({
            "type": "API_NEW_ISSUE",
            "severity": "MEDIUM",
            "service_name": service_name,
            "endpoint_url": endpoint_url,
            "resource_id": endpoint_url,
            "summary": f"{service_name} has new security issue"
        })
    
    return findings
```

#### Thêm API Endpoint để scan

Trong `secops_app/config.py`, thêm endpoint vào `OPENSTACK_API_ENDPOINTS`:

```python
OPENSTACK_API_ENDPOINTS = {
    # ... existing endpoints ...
    "NewService": "http://192.168.1.229:XXXX",
}
```

## 7. Bảo mật

### 7.1. Network Security
- Security groups chỉ cho phép truy cập từ admin_cidr và subnet nội bộ
- Gateway (obs_stack) có floating IP để truy cập từ bên ngoài
- Các instance khác chỉ truy cập được qua gateway (ProxyJump)

### 7.2. Credentials Management
- OpenStack credentials được lưu trong `openstack.env` với permission 600
- Không commit credentials vào git
- Sử dụng OpenRC file để generate credentials

### 7.3. Data Protection
- Database và logs được lưu trên mounted volumes
- Volumes có thể backup riêng biệt

## 8. Mở rộng và Cải tiến

### 8.1. Tính năng hiện có

#### Web Dashboard
- Modern, responsive UI với statistics cards
- Filter findings theo service, severity, status
- Real-time findings display
- AI suggestion generation với một click
- Approval workflow (approve/reject suggestions)

#### AI-Powered Suggestions
- Tích hợp OpenAI GPT-4
- Tự động generate remediation steps
- Context-aware recommendations
- Support approval workflow

#### API Endpoint Scanner
- Quét 12 OpenStack API endpoints
- Phát hiện nhiều loại security issues
- Configurable security checks
- Timeout handling

### 8.2. Tính năng có thể thêm
- Auto-remediation: Tự động sửa findings dựa trên approved suggestions
- Alert notifications: Slack, Email, PagerDuty
- More scanner rules: IAM policies, Network ACLs, etc.
- Multi-cloud support: AWS, Azure, GCP
- API authentication cho web dashboard
- Historical trends và charts
- Export findings (PDF, CSV)

### 8.2. Performance Optimization
- Parallel scanning
- Caching OpenStack connections
- Database indexing
- Metrics aggregation

## 9. Diagram Tổng hợp

### 9.1. Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  • Browser (Grafana Dashboard)                          │
│  • API Client (curl, Postman)                           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              obs_stack (Gateway)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Grafana  │  │Prometheus│  │   Loki   │  │AlertMgr ││
│  │  :3000   │  │  :9090   │  │  :3100   │  │  :9093  ││
│  └──────────┘  └────┬─────┘  └────┬─────┘  └─────────┘│
│                     │             │                    │
└─────────────────────┼─────────────┼────────────────────┘
                      │             │
        ┌─────────────┼─────────────┼─────────────┐
        │             │             │             │
┌───────▼──────┐ ┌───▼──────┐ ┌────▼──────┐ ┌───▼──────┐
│ secops_app   │ │ workload │ │ obs_stack │ │ obs_stack│
│              │ │          │ │ (agents)  │ │ (agents) │
│ SecOps API   │ │ Demo     │ │           │ │          │
│ :8000        │ │          │ │ Node Exp  │ │ Node Exp │
│              │ │          │ │ :9100     │ │ :9100    │
│              │ │          │ │ Promtail  │ │ Promtail │
└──────────────┘ └──────────┘ └───────────┘ └──────────┘
```

### 9.2. Data Flow Diagram

```
OpenStack Resources              OpenStack API Endpoints
        │                                │
        │ Scan (60s interval)            │ Scan (60s interval)
        ▼                                ▼
   SecOps API                      API Endpoint Scanner
        │                                │
        └────────────────┬───────────────┘
                         │
                         ▼
                  All Findings
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   SQLite DB      Prometheus         Logs
  (findings.db)    Metrics      (secops.log)
        │         (/metrics)            │
        │            │                  │
        │            └──► Grafana       │
        │            (Query)            │
        │                                │
        │                                ▼
        │                           Promtail
        │                                │
        │                                ▼
        │                              Loki
        │                                │
        │                                └──► Grafana (LogQL)
        │
        └──► Web Dashboard (/)
             • View findings
             • Generate suggestions
             • Approval workflow
```

## 10. Kết luận

Hệ thống cung cấp giải pháp tự động hóa hoàn chỉnh cho việc giám sát và phát hiện misconfigurations bảo mật trong OpenStack, với khả năng mở rộng và tích hợp dễ dàng với các công cụ observability hiện đại.

**Tính năng nổi bật:**
- Dual-layer scanning: OpenStack resources + API endpoints
- AI-powered remediation suggestions với OpenAI integration
- Modern web dashboard với real-time findings display
- Comprehensive observability stack (Prometheus, Loki, Grafana)
- Approval workflow cho security remediations
- Extensible architecture cho việc thêm scanner rules mới

