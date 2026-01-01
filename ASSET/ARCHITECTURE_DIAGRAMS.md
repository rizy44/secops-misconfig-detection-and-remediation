# SecOps Dashboard - System Architecture

## Complete System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          User/Admin (Browser)                           │
│                     http://localhost:8000 (via SSH tunnel)              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ HTTP
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                      SecOps Web Dashboard                               │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │Statistics  │  │   Filters    │  │   Findings   │  │  Suggestions │ │
│  │  Cards     │  │   Service    │  │    Table     │  │    Modal     │ │
│  └────────────┘  │  Severity    │  └──────────────┘  └──────────────┘ │
│                  │   Status     │                                      │
│                  └──────────────┘                                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ REST API
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                         FastAPI Backend                                 │
│                      (secops_app - port 8000)                          │
│                                                                         │
│  API Routes:                    Background Jobs:                       │
│  ├─ GET  /                      ├─ APScheduler (60s interval)         │
│  ├─ GET  /api/findings          │  └─ run_scan()                      │
│  ├─ GET  /api/services          │                                      │
│  ├─ POST /api/scan              Modules:                               │
│  ├─ POST /api/suggestions/{id}  ├─ config.py                          │
│  ├─ GET  /api/suggestions       ├─ scanners/api_endpoint_scanner.py   │
│  ├─ POST /api/.../approve       ├─ services/openai_service.py         │
│  └─ POST /api/.../reject        └─ Existing OpenStack scanners        │
│                                                                         │
└────┬────────────────┬───────────────────┬──────────────────────────────┘
     │                │                   │
     │                │                   │
     ▼                ▼                   ▼
┌─────────┐    ┌──────────────┐    ┌────────────┐
│ SQLite  │    │   OpenAI     │    │ OpenStack  │
│  DB     │    │    API       │    │    API     │
│         │    │   (GPT-4)    │    │ Endpoints  │
└─────────┘    └──────────────┘    └────────────┘
findings.db                         12 Services:
├─findings                          ├─Cloudformation
├─suggestions                       ├─Compute
└─api_endpoints                     ├─Identity
                                    ├─Network
                                    ├─Image
                                    ├─Orchestration
                                    ├─Placement
                                    ├─Share
                                    ├─Volumev3
                                    └─etc.
```

## Data Flow Diagram

```
1. SCANNING FLOW
═════════════════

Scheduler (60s) ──┐
                  │
                  ├──> OpenStack Resource Scanner
                  │    ├─ Security Groups
                  │    ├─ Servers
                  │    └─ Volumes
                  │
                  └──> API Endpoint Scanner
                       ├─ Check Auth
                       ├─ Check Headers
                       ├─ Check Methods
                       ├─ Check Version
                       └─ Check Protocol
                       │
                       ▼
                  All Findings
                       │
                       ▼
                  Database INSERT
                  (findings table)


2. SUGGESTION FLOW
═══════════════════

User clicks "Get Suggestion"
          │
          ▼
Check existing suggestion ─┬─> Exists ──> Display
          │                │
          └─> Not exists   │
                ▼          │
          Call OpenAI API  │
                ▼          │
          Generate text    │
                ▼          │
          Save to DB       │
          (suggestions)    │
                │          │
                └──────────┘
                ▼
          Display in Modal


3. APPROVAL FLOW
═════════════════

User reviews suggestion
          │
    ┌─────┴─────┐
    ▼           ▼
 Approve     Reject
    │           │
    ▼           ▼
Update         Update
status to      status to
'approved'     'rejected'
    │           │
    ▼           ▼
Update finding status
    │
    ▼
Refresh dashboard
```

## Component Interactions

```
┌──────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ Requests (AJAX)
                   ▼
         ┌─────────────────────┐
         │   Static Files      │
         │  ├─ index.html      │
         │  ├─ style.css       │
         │  └─ app.js          │
         └─────────┬───────────┘
                   │
                   │ Calls API
                   ▼
         ┌─────────────────────┐
         │   FastAPI Routes    │
         │  ├─ @app.get("/")   │
         │  ├─ @app.get("/api")│
         │  └─ @app.post(..)   │
         └─────────┬───────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
  ┌─────────┐ ┌────────┐ ┌─────────┐
  │Database │ │Scanner │ │ OpenAI  │
  │ Layer   │ │ Module │ │ Service │
  └─────────┘ └────────┘ └─────────┘
```

## Database Schema

```
┌─────────────────────────────────────┐
│           findings                  │
├─────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY │
│ ts              INTEGER             │
│ ftype           TEXT                │
│ severity        TEXT                │
│ resource_id     TEXT                │
│ summary         TEXT                │
│ service_name    TEXT         [NEW]  │
│ endpoint_url    TEXT         [NEW]  │
│ status          TEXT         [NEW]  │
└───────────────┬─────────────────────┘
                │
                │ FK: finding_id
                ▼
┌─────────────────────────────────────┐
│          suggestions         [NEW]  │
├─────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY │
│ finding_id      INTEGER FK          │
│ suggestion_text TEXT                │
│ status          TEXT                │
│ created_at      INTEGER             │
│ updated_at      INTEGER             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│        api_endpoints         [NEW]  │
├─────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY │
│ service_name    TEXT UNIQUE         │
│ endpoint_url    TEXT                │
│ last_scanned    INTEGER             │
│ status          TEXT                │
└─────────────────────────────────────┘
```

## Security Model

```
┌──────────────────────────────────────────────┐
│         Admin Network (172.10.0.0/16)        │
│              Your Computer                   │
└────────────────┬─────────────────────────────┘
                 │
                 │ SSH + Port Forward
                 │ (8000:10.10.50.163:8000)
                 ▼
┌──────────────────────────────────────────────┐
│    obs_stack (Gateway)                       │
│    Floating IP: 172.10.0.170                 │
│    Security Groups:                          │
│    ├─ SSH from admin_cidr                    │
│    └─ Grafana (3000) from admin_cidr         │
└────────────────┬─────────────────────────────┘
                 │
                 │ Internal Network
                 │ (10.10.50.0/24)
                 ▼
┌──────────────────────────────────────────────┐
│    secops_app (10.10.50.163)                 │
│    Security Groups:                          │
│    ├─ SSH from admin_cidr                    │
│    ├─ Port 8000 from subnet             [OLD]│
│    └─ Port 8000 from admin_cidr         [NEW]│
│                                              │
│    Services:                                 │
│    └─ FastAPI (port 8000)                    │
│       ├─ Web Dashboard                       │
│       ├─ API Endpoints                       │
│       └─ Scanner + OpenAI                    │
└──────────────────────────────────────────────┘
```

## Finding Types & Severity

```
┌───────────────────────────────────────────────────────────────┐
│                    Finding Categories                         │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  OpenStack Resources:                                         │
│  ├─ SG_OPEN_SSH              [HIGH]    - SSH open to world   │
│  ├─ NOVA_SERVER_ERROR        [MEDIUM]  - Server in ERROR     │
│  └─ CINDER_VOLUME_ERROR      [MEDIUM]  - Volume error        │
│                                                               │
│  API Endpoints (NEW):                                         │
│  ├─ API_UNAUTHENTICATED      [HIGH]    - No auth required    │
│  ├─ API_MISSING_HEADERS      [MEDIUM]  - Security headers    │
│  ├─ API_VERSION_DISCLOSURE   [LOW]     - Version exposed     │
│  ├─ API_DANGEROUS_METHODS    [MEDIUM]  - TRACE/TRACK allowed │
│  ├─ API_INSECURE_PROTOCOL    [HIGH]    - HTTP not HTTPS      │
│  ├─ API_TIMEOUT              [LOW]     - Endpoint timeout    │
│  └─ API_SCAN_ERROR           [LOW]     - Scan failure        │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

```
┌────────────────────────────────────────────────────────┐
│              Development/Admin Machine                 │
│                                                        │
│  Project Structure:                                    │
│  ├─ terraform/                                         │
│  │  ├─ main.tf              [MODIFIED]                │
│  │  └─ ...                                            │
│  ├─ ansible/                                           │
│  │  ├─ 04-secops-app.yml                              │
│  │  └─ inventory.ini                                  │
│  └─ secops_app/                                        │
│     ├─ app.py               [MODIFIED]                │
│     ├─ config.py            [NEW]                     │
│     ├─ requirements.txt     [MODIFIED]                │
│     ├─ docker-compose.yml   [MODIFIED]                │
│     ├─ scanners/            [NEW]                     │
│     ├─ services/            [NEW]                     │
│     └─ static/              [NEW]                     │
│                                                        │
└──────────────────┬─────────────────────────────────────┘
                   │
                   │ terraform apply
                   │ ansible-playbook
                   ▼
┌────────────────────────────────────────────────────────┐
│              OpenStack Infrastructure                  │
│                                                        │
│  ┌──────────────────────────────────────────────┐     │
│  │  secops_app VM (10.10.50.163)                │     │
│  │                                              │     │
│  │  /opt/secops/secops_app/                    │     │
│  │  ├─ app.py                                  │     │
│  │  ├─ config.py                               │     │
│  │  ├─ scanners/                               │     │
│  │  ├─ services/                               │     │
│  │  ├─ static/                                 │     │
│  │  ├─ requirements.txt                        │     │
│  │  ├─ docker-compose.yml                      │     │
│  │  └─ openstack.env  (with OPENAI_API_KEY)   │     │
│  │                                              │     │
│  │  Docker Container:                          │     │
│  │  └─ secops_api (python:3.11-slim)          │     │
│  │     └─ Running: uvicorn app:app --port 8000│     │
│  │                                              │     │
│  │  Data Volume:                                │     │
│  │  /data/secops/                              │     │
│  │  ├─ findings.db                             │     │
│  │  └─ secops.log                              │     │
│  └──────────────────────────────────────────────┘     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

This architecture provides a complete overview of the SecOps Dashboard system!




