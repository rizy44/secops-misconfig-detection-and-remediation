# System Diagrams - Hướng dẫn Vẽ Hình

File này chứa các diagram dạng text và hướng dẫn để vẽ hình cho báo cáo.

## 1. Kiến trúc Tổng quan (High-level Architecture)

### ASCII Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenStack Cloud                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  External Network (public1)                          │  │
│  │  ┌────────────────────────────────────────────────┐ │  │
│  │  │  Router (Gateway: 10.10.50.1)                  │ │  │
│  │  │  ┌──────────────────────────────────────────┐ │ │  │
│  │  │  │  Tenant Network: 10.10.50.0/24          │ │ │  │
│  │  │  │                                           │ │ │  │
│  │  │  │  ┌──────────────┐  ┌──────────────┐     │ │ │  │
│  │  │  │  │  obs_stack   │  │  secops_app  │     │ │ │  │
│  │  │  │  │  (Gateway)   │  │              │     │ │ │  │
│  │  │  │  │              │  │              │     │ │ │  │
│  │  │  │  │ • Grafana    │  │ • SecOps API │     │ │ │  │
│  │  │  │  │ • Prometheus │  │ • Scanner    │     │ │ │  │
│  │  │  │  │ • Loki       │  │ • Scheduler  │     │ │ │  │
│  │  │  │  │ • AlertMgr   │  │ • Database   │     │ │ │  │
│  │  │  │  │              │  │              │     │ │ │  │
│  │  │  │  │ 10.10.50.60  │  │ 10.10.50.163 │     │ │ │  │
│  │  │  │  │ FIP:172.10.  │  │              │     │ │ │  │
│  │  │  │  │   0.170      │  │              │     │ │ │  │
│  │  │  │  └──────────────┘  └──────────────┘     │ │ │  │
│  │  │  │         │                  │            │ │ │  │
│  │  │  │         └──────────┬───────┘            │ │ │  │
│  │  │  │                    │                    │ │ │  │
│  │  │  │         ┌──────────▼──────────┐        │ │ │  │
│  │  │  │         │    workload          │        │ │ │  │
│  │  │  │         │  (Demo Misconfig)   │        │ │ │  │
│  │  │  │         │  10.10.50.233       │        │ │ │  │
│  │  │  │         └─────────────────────┘        │ │ │  │
│  │  │  └──────────────────────────────────────────┘ │ │  │
│  │  └────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Mô tả để vẽ bằng công cụ (Draw.io, Lucidchart, etc.)

**Layers:**
1. **External Layer**: OpenStack Cloud (hình chữ nhật lớn)
2. **Network Layer**: 
   - External Network (public1) - hình chữ nhật
   - Router (Gateway) - hình router/switch
   - Tenant Network (10.10.50.0/24) - hình cloud/network
3. **Instance Layer**: 3 VMs
   - obs_stack (Gateway) - hình server với icon Grafana, Prometheus, Loki
   - secops_app - hình server với icon API, Scanner
   - workload - hình server với label "Demo Misconfig"

**Connections:**
- Router kết nối External Network và Tenant Network
- 3 VMs trong Tenant Network
- obs_stack có Floating IP (172.10.0.170)

## 2. Data Flow Diagram

### ASCII Diagram

```
┌─────────────┐
│  OpenStack  │
│  Resources  │
│             │
│ • Servers   │
│ • Security  │
│   Groups    │
│ • Volumes   │
└──────┬──────┘
       │
       │ Scan (mỗi 60s)
       │
┌──────▼─────────────────────────────────────┐
│         SecOps API (secops_app)            │
│  ┌──────────────────────────────────────┐  │
│  │  OpenStack Resource Scanner:         │  │
│  │  • scan_security_groups()            │  │
│  │  • scan_servers()                    │  │
│  │  • scan_volumes()                    │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  API Endpoint Scanner:               │  │
│  │  • Quét 12 OpenStack API endpoints   │  │
│  │  • Phát hiện unauthenticated access  │  │
│  │  • Kiểm tra security headers         │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │  OpenAI Service:                     │  │
│  │  • Generate remediation suggestions  │  │
│  └──────────────────────────────────────┘  │
│              │                             │
│              │ Findings                    │
│              │                             │
│  ┌───────────▼───────────┐                 │
│  │  SQLite Database      │                 │
│  │  (findings.db)        │                 │
│  └───────────┬───────────┘                 │
│              │                             │
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

### Mô tả để vẽ

**Components:**
1. **OpenStack Resources** (hình cloud/database) - Security Groups, Servers, Volumes
2. **OpenStack API Endpoints** (hình API/service) - 12 API endpoints (Compute, Network, Identity, etc.)
3. **SecOps API** (hình server/API gateway)
   - OpenStack Resource Scanner (hình process/function)
   - API Endpoint Scanner (hình process/function)
   - OpenAI Service (hình AI/brain icon)
   - SQLite Database (hình database)
   - Prometheus Metrics (hình metrics/gauge)
   - Logs (hình file/document)
   - Web Dashboard (hình browser/monitor)
4. **Prometheus** (hình database/time-series DB)
5. **Loki** (hình database/log DB)
6. **Grafana** (hình dashboard/monitor)

**Flows:**
- Resource scan flow: OpenStack Resources → SecOps API (mũi tên "Scan every 60s")
- API scan flow: OpenStack API Endpoints → API Endpoint Scanner (mũi tên "Scan every 60s")
- Data storage: SecOps API → SQLite (mũi tên "Findings")
- Metrics export: SecOps API → Prometheus (mũi tên "Metrics")
- Logs export: SecOps API → Loki (mũi tên "Logs")
- Visualization: Prometheus + Loki → Grafana (mũi tên "Query")
- Web Dashboard: SQLite → Web Dashboard (mũi tên "Query findings")
- AI Suggestions: Web Dashboard → OpenAI Service → SQLite (mũi tên "Generate suggestions")

## 3. Deployment Flow

### ASCII Diagram

```
┌─────────────────┐
│  Terraform      │
│  terraform.tfvars│
└────────┬────────┘
         │
         │ terraform apply
         │
         ▼
┌─────────────────────────────────────┐
│  Infrastructure Created             │
│  • Network, Subnet, Router          │
│  • Security Groups                  │
│  • Instances (3 VMs)                │
│  • Volumes                          │
│  • Floating IPs                     │
│  • Ansible Inventory (auto-gen)     │
└────────┬────────────────────────────┘
         │
         │ ansible-playbook
         │
         ▼
┌─────────────────────────────────────┐
│  Ansible Playbooks (Sequential)     │
│                                     │
│  1. 00-mount-data.yml              │
│     └─► Mount volumes               │
│                                     │
│  2. 01-docker.yml                   │
│     └─► Install Docker              │
│                                     │
│  3. 02-obs-stack.yml                │
│     └─► Deploy Observability        │
│                                     │
│  4. 03-agents.yml                   │
│     └─► Deploy Agents               │
│                                     │
│  5. 04-secops-app.yml              │
│     └─► Deploy Scanner             │
└────────┬────────────────────────────┘
         │
         │ Services Start
         │
         ▼
┌─────────────────────────────────────┐
│  Running System                     │
│  • Grafana Dashboard                │
│  • Prometheus Scraping              │
│  • Loki Collecting Logs             │
│  • SecOps Resource Scanner          │
│  • API Endpoint Scanner             │
│  • Web Dashboard                    │
│  • OpenAI Service Ready             │
└─────────────────────────────────────┘
```

### Mô tả để vẽ

**Phases:**
1. **Terraform Phase** (hình công cụ Terraform)
   - Input: terraform.tfvars
   - Output: Infrastructure + Inventory

2. **Ansible Phase** (hình công cụ Ansible)
   - 5 playbooks theo thứ tự (hình flowchart)
   - Mỗi playbook có output riêng

3. **Running Phase** (hình hệ thống đang chạy)
   - Các services đang active

**Connections:**
- Terraform → Infrastructure (mũi tên "terraform apply")
- Infrastructure → Ansible (mũi tên "ansible-playbook")
- Ansible → Running System (mũi tên "Services Start")

## 4. Component Interaction Diagram

### ASCII Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User/Admin                           │
│                    (Browser/API Client)                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTPS (port 3000)
                     │
        ┌────────────▼────────────┐
        │      Grafana            │
        │      (obs_stack)        │
        │  • Dashboards           │
        │  • Logs View            │
        └─────┬───────────┬───────┘
              │           │
              │ Query     │ Query
              │           │
    ┌─────────▼───┐  ┌────▼─────────┐
    │ Prometheus  │  │     Loki     │
    │ (obs_stack) │  │ (obs_stack)  │
    └─────┬───────┘  └──────┬───────┘
          │                  │
          │ Scrape           │ Push
          │                  │
    ┌─────▼──────────────────▼───────┐
    │  Monitoring Agents              │
    │  • Node Exporter (all hosts)    │
    │  • Promtail (all hosts)         │
    └─────────────────────────────────┘
              │
              │ Collect
              │
    ┌─────────▼──────────┐
    │   secops_app        │
    │  • SecOps API       │
    │  • Resource Scanner │
    │  • API Scanner      │
    │  • Web Dashboard    │
    │  • OpenAI Service   │
    │  • Metrics Export   │
    │  • Logs             │
    └─────────┬───────────┘
              │
              │ Scan
              │
    ┌─────────▼──────────┐
    │   OpenStack API    │
    │  • Nova            │
    │  • Neutron         │
    │  • Cinder          │
    │  • Keystone        │
    │  • Glance          │
    │  • Heat            │
    │  • ... (12 APIs)   │
    └────────────────────┘
```

### Mô tả để vẽ

**Layers từ trên xuống:**
1. **User Layer**: Browser/API Client
2. **Visualization Layer**: Grafana
3. **Storage Layer**: Prometheus, Loki
4. **Collection Layer**: Node Exporter, Promtail
5. **Application Layer**: SecOps API
6. **Infrastructure Layer**: OpenStack API

**Interactions:**
- User → Grafana: HTTPS (port 3000)
- User → Web Dashboard: HTTP (port 8000)
- Grafana → Prometheus: Query API
- Grafana → Loki: LogQL Query
- Prometheus → Agents: Scrape metrics
- Loki ← Promtail: Push logs
- SecOps API → OpenStack Resources: Scan API calls (Nova, Neutron, Cinder)
- SecOps API → OpenStack API Endpoints: HTTP requests (12 endpoints)
- SecOps API → Prometheus: Export metrics
- SecOps API → Logs: Write to file
- Web Dashboard → SecOps API: Query findings via REST API
- Web Dashboard → OpenAI Service: Generate suggestions
- OpenAI Service → SecOps API: Save suggestions to database

## 5. Security Groups Diagram

### ASCII Diagram

```
┌─────────────────────────────────────────────────────────┐
│              Security Groups Configuration              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  obs_stack (Gateway)                                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_ssh_admin                                      │  │
│  │  • SSH (22) from 172.10.0.0/16                  │  │
│  │  • SSH (22) from 10.10.50.0/24                  │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_obs_public                                     │  │
│  │  • Grafana (3000) from 172.10.0.0/16             │  │
│  │  • Grafana (3000) from 10.10.50.0/24             │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_internal                                       │  │
│  │  • Prometheus (9090) from 10.10.50.0/24          │  │
│  │  • Loki (3100) from 10.10.50.0/24                │  │
│  │  • Node Exporter (9100) from 10.10.50.0/24       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  secops_app                                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_ssh_admin                                      │  │
│  │  • SSH (22) from 172.10.0.0/16                   │  │
│  │  • SSH (22) from 10.10.50.0/24                  │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_internal                                       │  │
│  │  • SecOps API (8000) from 10.10.50.0/24         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  workload (Demo Misconfig)                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_ssh_admin                                      │  │
│  │  • SSH (22) from 172.10.0.0/16                   │  │
│  │  • SSH (22) from 10.10.50.0/24                  │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ sg_demo_misconfig                                 │  │
│  │  • SSH (22) from 0.0.0.0/0 ⚠️                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Mô tả để vẽ

**Structure:**
- 3 sections cho 3 instances
- Mỗi instance có các security groups (hình boxes)
- Mỗi security group có rules (hình list)
- Highlight rule misconfig với icon warning

## 6. Hướng dẫn Vẽ bằng Công cụ

### Draw.io / diagrams.net

1. **Tạo file mới**: https://app.diagrams.net/
2. **Chọn template**: 
   - Network Diagram cho architecture
   - Flowchart cho deployment flow
   - Sequence Diagram cho interactions

3. **Icons/Shapes cần dùng:**
   - Server/VM: `Server` hoặc `Cloud Server`
   - Network: `Network` hoặc `Cloud`
   - Router: `Router` hoặc `Switch`
   - Database: `Database` hoặc `Cylinder`
   - API: `API` hoặc `Web Service`
   - Dashboard: `Monitor` hoặc `Dashboard`

4. **Colors:**
   - obs_stack: Blue
   - secops_app: Green
   - workload: Orange/Red (vì có misconfig)
   - Network: Gray
   - External: Light Blue

### Lucidchart

1. Tương tự Draw.io
2. Có template sẵn cho AWS/Azure, có thể adapt cho OpenStack

### PowerPoint / Google Slides

1. Sử dụng SmartArt cho flowcharts
2. Shapes cơ bản cho architecture
3. Connectors cho relationships

## 7. API Endpoints Being Scanned

Hệ thống quét 12 OpenStack API endpoints:

1. **Cloudformation** - `http://192.168.1.229:8000/v1`
2. **Compute** - `http://192.168.1.229:8774/v2.1`
3. **Compute_Legacy** - `http://192.168.1.229:8774/v2/...`
4. **Container_Infra** - `http://192.168.1.229:9511/v1`
5. **Identity** - `http://192.168.1.229:5000`
6. **Image** - `http://192.168.1.229:9292`
7. **Network** - `http://192.168.1.229:9696`
8. **Orchestration** - `http://192.168.1.229:8004/v1/...`
9. **Placement** - `http://192.168.1.229:8780`
10. **Share** - `http://192.168.1.229:8786/v1/...`
11. **Sharev2** - `http://192.168.1.229:8786/v2`
12. **Volumev3** - `http://192.168.1.229:8776/v3/...`

**Security Checks Performed:**
- Authentication requirements (401/403 responses)
- Security headers (X-Content-Type-Options, X-Frame-Options)
- Version information disclosure
- Dangerous HTTP methods (TRACE, TRACK)
- Protocol security (HTTP vs HTTPS)
- Request timeout handling

## 8. Mẫu Diagram cho Báo cáo

### Slide 1: System Overview
- High-level Architecture (Diagram 1)
- 4 main components: Infrastructure, Observability, Scanner, AI Service

### Slide 2: Network Architecture
- Network Diagram (Diagram 1 - Network part)
- Security Groups (Diagram 5)

### Slide 3: Data Flow
- Data Flow Diagram (Diagram 2)
- Scanning Flow

### Slide 4: Deployment Process
- Deployment Flow (Diagram 3)
- Steps và timeline

### Slide 5: Component Interactions
- Component Interaction (Diagram 4)
- Services và protocols

### Slide 6: Security Scanning Capabilities
- API Endpoint Scanner (12 endpoints)
- Security checks performed
- Findings types và severity levels

### Slide 7: AI-Powered Workflow
- Web Dashboard interface
- AI suggestion generation
- Approval workflow

## 9. Tips cho Báo cáo

1. **Consistency**: Dùng cùng color scheme cho tất cả diagrams
2. **Labels**: Đảm bảo tất cả components có labels rõ ràng
3. **Legends**: Thêm legend cho colors và line styles
4. **Annotations**: Thêm notes cho các điểm quan trọng
5. **Version**: Đánh số version cho diagrams nếu có nhiều iterations

