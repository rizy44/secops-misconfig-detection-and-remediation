import os, time, sqlite3, logging
from typing import List, Dict, Optional
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from openstack import connection
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Import new modules
import config
import json
from scanners.api_endpoint_scanner import APIEndpointScanner
from scanners.openstack_exposure_scanner import scan_floating_ips, scan_port_security
from scanners.os_baseline_scanner import scan_os_baseline
# OpenAI service removed - using rule-based remediation
from services.normalize import normalize_finding
from services.remediation_engine import RemediationEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("secops")
LOG_PATH = os.environ.get("SECOPS_LOG", "/data/secops/secops.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

fh = logging.FileHandler(LOG_PATH)
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.getLogger().addHandler(fh)   #  add vào logger "secops" 

DB_PATH = os.environ.get("SECOPS_DB", "/data/secops/findings.db")
SCAN_INTERVAL_SEC = int(os.environ.get("SCAN_INTERVAL_SEC", "60"))

# Note: OpenAI service has been removed - using rule-based remediation engine only

# Initialize Remediation Engine
catalog_path = os.path.join(os.path.dirname(__file__), "remediation", "catalog.yml")
remediation_engine = RemediationEngine(catalog_path, DB_PATH)

FINDINGS = Counter("secops_findings_total", "Findings total", ["type", "severity"])
SCAN_TIME = Histogram("secops_scan_duration_seconds", "Scan duration seconds")

app = FastAPI(title="secops-api")

def db_init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        # Create findings table (check if exists first)
        con.execute("""
        CREATE TABLE IF NOT EXISTS findings(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER,
          ftype TEXT,
          severity TEXT,
          resource_id TEXT,
          summary TEXT
        )
        """)
        
        # Add new columns if they don't exist (for existing databases)
        # This ensures backward compatibility with old databases
        migrations = [
            ("service_name", "TEXT DEFAULT ''"),
            ("endpoint_url", "TEXT DEFAULT ''"),
            ("status", "TEXT DEFAULT 'new'"),
            ("details_json", "TEXT DEFAULT ''"),
            ("resolved_at", "INTEGER DEFAULT NULL")
        ]
        
        for col_name, col_def in migrations:
            try:
                con.execute(f"ALTER TABLE findings ADD COLUMN {col_name} {col_def}")
                log.info(f"Added column: {col_name}")
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        # Update existing rows to have default values
        try:
            con.execute("UPDATE findings SET status = 'new' WHERE status IS NULL OR status = ''")
            con.execute("UPDATE findings SET service_name = '' WHERE service_name IS NULL")
            con.execute("UPDATE findings SET endpoint_url = '' WHERE endpoint_url IS NULL")
            con.execute("UPDATE findings SET details_json = '' WHERE details_json IS NULL")
        except sqlite3.OperationalError:
            pass  # Column might not exist yet
        
        # Suggestions table
        con.execute("""
        CREATE TABLE IF NOT EXISTS suggestions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          finding_id INTEGER,
          suggestion_text TEXT,
          status TEXT DEFAULT 'pending',
          created_at INTEGER,
          updated_at INTEGER,
          FOREIGN KEY(finding_id) REFERENCES findings(id)
        )
        """)
        
        # API endpoints table
        con.execute("""
        CREATE TABLE IF NOT EXISTS api_endpoints(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          service_name TEXT UNIQUE,
          endpoint_url TEXT,
          last_scanned INTEGER,
          status TEXT DEFAULT 'active'
        )
        """)
        
        # Remediation runs table
        con.execute("""
        CREATE TABLE IF NOT EXISTS remediation_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          finding_id INTEGER,
          runbook_id TEXT,
          status TEXT,
          started_at INTEGER,
          finished_at INTEGER,
          stdout TEXT,
          stderr TEXT,
          FOREIGN KEY(finding_id) REFERENCES findings(id)
        )
        """)
        
        con.commit()

def db_insert(items: List[Dict]):
    import json
    with sqlite3.connect(DB_PATH) as con:
        for it in items:
            # Check if details_json column exists
            cur = con.execute("PRAGMA table_info(findings)")
            columns = [row[1] for row in cur.fetchall()]
            has_details_json = "details_json" in columns
            
            if has_details_json:
                details_json = json.dumps(it.get("details_json", {}), ensure_ascii=False)
                con.execute(
                    """INSERT INTO findings(ts, ftype, severity, resource_id, summary, service_name, endpoint_url, status, details_json) 
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        int(time.time()), 
                        it["type"], 
                        it["severity"], 
                        it["resource_id"], 
                        it["summary"],
                        it.get("service_name", ""),
                        it.get("endpoint_url", ""),
                        "new",
                        details_json
                    )
                )
            else:
                # Fallback for old schema
                con.execute(
                    """INSERT INTO findings(ts, ftype, severity, resource_id, summary, service_name, endpoint_url, status) 
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        int(time.time()), 
                        it["type"], 
                        it["severity"], 
                        it["resource_id"], 
                        it["summary"],
                        it.get("service_name", ""),
                        it.get("endpoint_url", ""),
                        "new"
                    )
                )
        con.commit()

def get_conn():
    # Load env vars from file if not already in environment
    env_file = os.path.join(os.path.dirname(__file__), "openstack.env")
    
    if os.path.exists(env_file):
        log.info(f"Loading env vars from {env_file}")
        loaded_count = 0
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    # Always set, don't check if exists (may need to override)
                    os.environ[key] = value
                    loaded_count += 1
        log.info(f"Loaded {loaded_count} environment variables from file")
    else:
        log.warning(f"Env file not found: {env_file}")
    
    # Get required env vars
    auth_url = os.environ.get("OS_AUTH_URL")
    username = os.environ.get("OS_USERNAME")
    password = os.environ.get("OS_PASSWORD")
    project_name = os.environ.get("OS_PROJECT_NAME")
    user_domain_name = os.environ.get("OS_USER_DOMAIN_NAME", "Default")
    project_domain_name = os.environ.get("OS_PROJECT_DOMAIN_NAME", "Default")
    region_name = os.environ.get("OS_REGION_NAME")
    identity_api_version = os.environ.get("OS_IDENTITY_API_VERSION", "3")
    
    # Log current state for debugging
    log.info("=== OpenStack Connection Debug ===")
    log.info(f"OS_AUTH_URL: {auth_url}")
    log.info(f"OS_USERNAME: {username}")
    log.info(f"OS_PASSWORD: {'SET' if password else 'NOT SET'}")
    log.info(f"OS_PROJECT_NAME: {project_name}")
    log.info(f"OS_USER_DOMAIN_NAME: {user_domain_name}")
    log.info(f"OS_PROJECT_DOMAIN_NAME: {project_domain_name}")
    log.info(f"OS_REGION_NAME: {region_name}")
    
    # Verify required vars
    required = ["OS_AUTH_URL", "OS_USERNAME", "OS_PASSWORD", "OS_PROJECT_NAME"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        log.error(f"Missing required env vars: {missing}")
        log.error(f"Available OS_* vars: {[k for k in os.environ.keys() if k.startswith('OS_')]}")
        raise ValueError(f"Missing required OpenStack env vars: {missing}")
    
    # Try to create connection with explicit parameters first
    try:
        log.info("Creating OpenStack connection with explicit parameters...")
        conn = connection.Connection(
            auth_url=auth_url,
            username=username,
            password=password,
            project_name=project_name,
            user_domain_name=user_domain_name,
            project_domain_name=project_domain_name,
            region_name=region_name,
            identity_api_version=identity_api_version,
        )
        log.info("OpenStack connection created successfully")
        return conn
    except Exception as e:
        log.warning(f"Failed with explicit parameters: {e}, trying default Connection()...")
        # Fallback to default Connection() which reads from env
        try:
            conn = connection.Connection()
            log.info("OpenStack connection created successfully (using env vars)")
            return conn
        except Exception as e2:
            log.error(f"Failed to create OpenStack connection: {e2}")
            log.error(f"Available OS_* vars: {[k for k in os.environ.keys() if k.startswith('OS_')]}")
            raise

def scan_security_groups(conn):
    import json
    findings = []
    for sg in conn.network.security_groups():
        for rule in sg.security_group_rules:
            if rule.get("direction") != "ingress":
                continue
            if rule.get("ethertype") != "IPv4":
                continue
            remote = rule.get("remote_ip_prefix")
            proto  = rule.get("protocol")
            pmin   = rule.get("port_range_min")
            pmax   = rule.get("port_range_max")

            # Check for world-open sensitive ports
            if remote == "0.0.0.0/0" and proto == "tcp" and pmin == pmax:
                port = pmin
                finding_type = None
                
                # SSH
                if port == 22:
                    finding_type = "SG_OPEN_SSH"  # Keep legacy for backward compatibility
                # RDP
                elif port == 3389:
                    finding_type = "SG_OPEN_RDP"
                # Database ports
                elif port in config.SENSITIVE_PORTS:
                    finding_type = "SG_WORLD_OPEN_DB_PORT"
                
                if finding_type:
                    details = {
                        "sg_id": sg.id,
                        "sg_name": sg.name,
                        "rule_id": rule.get("id"),
                        "protocol": proto,
                        "port_min": pmin,
                        "port_max": pmax,
                        "remote_ip_prefix": remote,
                        "project_id": sg.project_id
                    }
                    
                    # Determine severity
                    severity = "HIGH" if port in [22, 3389] else "MEDIUM"
                    
                    findings.append({
                        "type": finding_type,
                        "severity": severity,
                        "resource_id": sg.id,
                        "summary": f"SecurityGroup {sg.name} allows 0.0.0.0/0 tcp/{port}",
                        "details_json": details
                    })
    return findings

def scan_servers(conn):
    findings = []
    for srv in conn.compute.servers(details=True):
        # demo: ERROR instance
        status = (srv.status or "").upper()
        if status == "ERROR":
            findings.append({
                "type": "NOVA_SERVER_ERROR",
                "severity": "MEDIUM",
                "resource_id": srv.id,
                "summary": f"Server {srv.name} status=ERROR"
            })
    return findings

def scan_volumes(conn):
    findings = []
    for vol in conn.block_storage.volumes(details=True):
        st = (vol.status or "").lower()
        if st in ("error", "error_restoring", "error_extending", "error_deleting"):
            findings.append({
                "type": "CINDER_VOLUME_ERROR",
                "severity": "MEDIUM",
                "resource_id": vol.id,
                "summary": f"Volume {getattr(vol,'name','')} status={st}"
            })
    return findings

@SCAN_TIME.time()
def run_scan():
    try:
        conn = get_conn()
        all_findings = []
        
        # Existing OpenStack resource scans
        all_findings += scan_security_groups(conn)
        all_findings += scan_servers(conn)
        all_findings += scan_volumes(conn)
        
        # Extended exposure scans
        all_findings += scan_floating_ips(conn)
        all_findings += scan_port_security(conn)
        
        # OS baseline scans (if enabled)
        if config.OS_SCAN_ENABLED:
            try:
                os_findings = scan_os_baseline(conn, config.ANSIBLE_INVENTORY, config.OS_SCAN_TIMEOUT)
                all_findings += os_findings
                log.info(f"OS baseline scan completed: {len(os_findings)} findings")
            except Exception as e:
                log.error(f"OS baseline scanner error: {e}")
        
        # New API endpoint scans
        if config.API_SCAN_ENABLED:
            try:
                with APIEndpointScanner(config.OPENSTACK_API_ENDPOINTS, config.API_SCAN_TIMEOUT) as scanner:
                    api_findings = scanner.scan_all()
                    all_findings += api_findings
                    log.info(f"API scan completed: {len(api_findings)} findings")
            except Exception as e:
                log.error(f"API scanner error: {e}")

        if all_findings:
            for f in all_findings:
                FINDINGS.labels(f["type"], f["severity"]).inc()
            db_insert(all_findings)
            for f in all_findings:
                log.warning("FINDING %s %s %s", f["severity"], f["type"], f["summary"])
        else:
            log.info("Scan OK: no findings")

    except Exception as e:
        log.exception("Scan failed: %s", e)

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/findings")
def list_findings(
    limit: int = 50, 
    service: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None
):
    """List findings with optional filters"""
    try:
        with sqlite3.connect(DB_PATH) as con:
            # Check which columns exist (for backward compatibility)
            try:
                cur = con.execute("PRAGMA table_info(findings)")
                existing_columns = [row[1] for row in cur.fetchall()]
            except sqlite3.Error as e:
                log.error(f"Error checking table schema: {e}")
                raise HTTPException(status_code=500, detail=f"Database error: {e}")
            
            # Base columns (always present)
            base_columns = ["id", "ts", "ftype", "severity", "resource_id", "summary"]
            
            # Verify base columns exist
            missing_base = [col for col in base_columns if col not in existing_columns]
            if missing_base:
                log.error(f"Missing base columns: {missing_base}")
                raise HTTPException(status_code=500, detail=f"Database schema error: missing columns {missing_base}")
            
            # Optional columns (may not exist in old databases)
            optional_columns = []
            for col in ["service_name", "endpoint_url", "status"]:
                if col in existing_columns:
                    optional_columns.append(col)
            
            # Build SELECT query
            select_cols = base_columns + optional_columns
            query = f"""SELECT {', '.join(select_cols)} FROM findings WHERE 1=1"""
            params = []
            
            # Only filter by service if column exists
            if service and "service_name" in existing_columns:
                query += " AND service_name = ?"
                params.append(service)
            
            # Only filter by status if column exists
            if status and "status" in existing_columns:
                query += " AND status = ?"
                params.append(status)
            
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            try:
                cur = con.execute(query, params)
                rows = cur.fetchall()
            except sqlite3.Error as e:
                log.error(f"Error executing query: {e}, query: {query}, params: {params}")
                raise HTTPException(status_code=500, detail=f"Query error: {e}")
            
            # Convert to dict and add defaults for missing columns
            result = []
            for row in rows:
                try:
                    row_dict = dict(zip(select_cols, row))
                    
                    # Add defaults for missing columns
                    if "service_name" not in existing_columns:
                        row_dict["service_name"] = ""
                    if "endpoint_url" not in existing_columns:
                        row_dict["endpoint_url"] = ""
                    if "status" not in existing_columns:
                        row_dict["status"] = "new"
                    
                    result.append(row_dict)
                except Exception as e:
                    log.error(f"Error processing row: {e}, row: {row}")
                    continue
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Unexpected error in list_findings: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/findings/{finding_id}")
def get_finding(finding_id: int):
    """Get detailed finding by ID"""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Finding not found")
        
        return dict(row)


# Legacy endpoint for backward compatibility
@app.get("/findings")
def list_findings_legacy(limit: int = 50):
    """Legacy findings endpoint (backward compatibility)"""
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute(
            "SELECT ts, ftype, severity, resource_id, summary FROM findings ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
    return [{"ts": r[0], "type": r[1], "severity": r[2], "resource_id": r[3], "summary": r[4]} for r in rows]


@app.get("/api/services")
def list_services():
    """List all OpenStack services with findings"""
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute("""
            SELECT DISTINCT service_name, COUNT(*) as count 
            FROM findings 
            WHERE service_name != '' 
            GROUP BY service_name
            ORDER BY service_name
        """)
        rows = cur.fetchall()
    
    # Add configured services even if no findings
    services = {row[0]: row[1] for row in rows}
    for service_name in config.OPENSTACK_API_ENDPOINTS.keys():
        if service_name not in services:
            services[service_name] = 0
    
    return [{"name": k, "finding_count": v} for k, v in services.items()]


@app.post("/api/scan")
def trigger_scan():
    """Manually trigger a scan"""
    try:
        run_scan()
        return {"status": "success", "message": "Scan completed"}
    except Exception as e:
        log.error(f"Manual scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Note: Suggestions API endpoints have been removed as OpenAI integration is no longer used
# The system now uses rule-based remediation via the remediate endpoint below


@app.post("/api/remediate/{finding_id}")
def remediate_finding(finding_id: int, force: bool = False):
    """Remediate a finding (requires approved status unless force=true)"""
    
    # Get finding
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT * FROM findings WHERE id = ?", (finding_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Finding not found")
        
        finding = dict(row)
    
    # Check status
    if not force and finding.get("status") != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Finding status must be 'approved' to remediate (current: {finding.get('status')}). Use ?force=true to override."
        )
    
    # Normalize finding
    finding_norm = normalize_finding(finding)
    
    # Resolve runbook
    runbook_id = remediation_engine.resolve_runbook(finding_norm)
    if not runbook_id:
        raise HTTPException(
            status_code=404,
            detail=f"No runbook found for finding type: {finding_norm.get('type')}"
        )
    
    # Check approval requirement
    catalog = remediation_engine.catalog
    if runbook_id in catalog:
        runbook_def = catalog[runbook_id]
        if runbook_def.get("approval_required", True) and not force and finding.get("status") != "approved":
            raise HTTPException(
                status_code=400,
                detail="Runbook requires approval. Finding must be in 'approved' status."
            )
    
    # Get OpenStack connection
    try:
        conn = get_conn()
    except Exception as e:
        log.error(f"Failed to get OpenStack connection: {e}")
        raise HTTPException(status_code=500, detail=f"OpenStack connection failed: {e}")
    
    # Create remediation run record
    started_at = int(time.time())
    with sqlite3.connect(DB_PATH) as con:
        cur = con.execute(
            """INSERT INTO remediation_runs(finding_id, runbook_id, status, started_at)
               VALUES (?, ?, 'started', ?)""",
            (finding_id, runbook_id, started_at)
        )
        run_id = cur.lastrowid
        con.commit()
    
    # Update finding status
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "UPDATE findings SET status = 'remediating' WHERE id = ?",
            (finding_id,)
        )
        con.commit()
    
    # Execute runbook
    try:
        result = remediation_engine.execute_runbook(finding_id, runbook_id, finding_norm, conn)
        finished_at = int(time.time())
        
        # Update remediation run
        with sqlite3.connect(DB_PATH) as con:
            con.execute(
                """UPDATE remediation_runs 
                   SET status = ?, finished_at = ?, stdout = ?, stderr = ?
                   WHERE id = ?""",
                (result["status"], finished_at, result["stdout"], result["stderr"], run_id)
            )
            con.commit()
        
        # Update finding status based on result
        new_status = "remediated_unverified" if result["status"] == "success" else "remediation_failed"
        with sqlite3.connect(DB_PATH) as con:
            con.execute(
                "UPDATE findings SET status = ? WHERE id = ?",
                (new_status, finding_id)
            )
            con.commit()
        
        # If successful, run verification
        if result["status"] == "success":
            verify_ok = remediation_engine.verify_remediation(finding_id, runbook_id, finding_norm, conn)
            
            if verify_ok:
                # Update to verified
                with sqlite3.connect(DB_PATH) as con:
                    con.execute(
                        """UPDATE remediation_runs SET status = 'verified' WHERE id = ?""",
                        (run_id,)
                    )
                    con.execute(
                        """UPDATE findings SET status = 'resolved', resolved_at = ? WHERE id = ?""",
                        (finished_at, finding_id)
                    )
                    con.commit()
            else:
                # Verification failed
                with sqlite3.connect(DB_PATH) as con:
                    con.execute(
                        """UPDATE remediation_runs SET status = 'verify_failed' WHERE id = ?""",
                        (run_id,)
                    )
                    con.execute(
                        "UPDATE findings SET status = 'verify_failed' WHERE id = ?",
                        (finding_id,)
                    )
                    con.commit()
        
        return {
            "run_id": run_id,
            "status": result["status"],
            "message": "Remediation completed" if result["status"] == "success" else "Remediation failed"
        }
        
    except Exception as e:
        log.exception(f"Error during remediation: {e}")
        finished_at = int(time.time())
        with sqlite3.connect(DB_PATH) as con:
            con.execute(
                """UPDATE remediation_runs 
                   SET status = 'failed', finished_at = ?, stderr = ?
                   WHERE id = ?""",
                (finished_at, str(e), run_id)
            )
            con.execute(
                "UPDATE findings SET status = 'remediation_failed' WHERE id = ?",
                (finding_id,)
            )
            con.commit()
        raise HTTPException(status_code=500, detail=f"Remediation error: {e}")


@app.get("/api/remediation/{run_id}")
def get_remediation_run(run_id: int):
    """Get remediation run details by ID"""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT * FROM remediation_runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Remediation run not found")
        
        return dict(row)


@app.get("/api/remediation")
def list_remediation_runs(finding_id: Optional[int] = None):
    """List remediation runs with optional finding_id filter"""
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        
        if finding_id:
            cur = con.execute(
                "SELECT * FROM remediation_runs WHERE finding_id = ? ORDER BY id DESC",
                (finding_id,)
            )
        else:
            cur = con.execute("SELECT * FROM remediation_runs ORDER BY id DESC LIMIT 100")
        
        rows = cur.fetchall()
        return [dict(row) for row in rows]


@app.get("/")
async def root():
    """API endpoints information"""
    return {
        "service": "SecOps API",
        "version": "1.0",
        "endpoints": {
            "findings": {
                "list": "GET /api/findings?limit=50&severity=HIGH&service=Compute&status=new",
                "get": "GET /api/findings/{finding_id}",
                "create": "POST /api/scan"
            },
            "services": {
                "list": "GET /api/services"
            },
            "remediation": {
                "remediate": "POST /api/remediate/{finding_id}?force=false",
                "get_run": "GET /api/remediation/{run_id}",
                "list_runs": "GET /api/remediation?finding_id=123"
            },
            "metrics": "GET /metrics",
            "scan": "POST /api/scan"
        }
    }



@app.on_event("startup")
def startup():
    db_init()
    
    # Run migration on startup to ensure schema is up-to-date
    try:
        with sqlite3.connect(DB_PATH) as con:
            cur = con.execute("PRAGMA table_info(findings)")
            existing_columns = [row[1] for row in cur.fetchall()]
            
            # Add missing columns
            migrations = [
                ("service_name", "TEXT DEFAULT ''"),
                ("endpoint_url", "TEXT DEFAULT ''"),
                ("status", "TEXT DEFAULT 'new'"),
                ("details_json", "TEXT DEFAULT ''"),
                ("resolved_at", "INTEGER DEFAULT NULL")
            ]
            
            for col_name, col_def in migrations:
                if col_name not in existing_columns:
                    try:
                        con.execute(f"ALTER TABLE findings ADD COLUMN {col_name} {col_def}")
                        log.info(f"Migrated: Added column {col_name}")
                    except sqlite3.OperationalError as e:
                        log.debug(f"Column {col_name} migration: {e}")
            
            # Update existing rows
            try:
                con.execute("UPDATE findings SET status = 'new' WHERE status IS NULL OR status = ''")
                con.execute("UPDATE findings SET service_name = '' WHERE service_name IS NULL")
                con.execute("UPDATE findings SET endpoint_url = '' WHERE endpoint_url IS NULL")
                con.execute("UPDATE findings SET details_json = '' WHERE details_json IS NULL")
                con.commit()
            except sqlite3.OperationalError:
                pass  # Columns might not exist yet
            
            # Ensure remediation_runs table exists
            try:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS remediation_runs(
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      finding_id INTEGER,
                      runbook_id TEXT,
                      status TEXT,
                      started_at INTEGER,
                      finished_at INTEGER,
                      stdout TEXT,
                      stderr TEXT,
                      FOREIGN KEY(finding_id) REFERENCES findings(id)
                    )
                """)
                con.commit()
            except sqlite3.OperationalError as e:
                log.debug(f"Remediation_runs table migration: {e}")
    
    except Exception as e:
        log.warning(f"Migration on startup failed (non-fatal): {e}")
    
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(run_scan, "interval", seconds=SCAN_INTERVAL_SEC, max_instances=1)
    sched.start()
    log.info("Scheduler started, interval=%ss", SCAN_INTERVAL_SEC)
    run_scan()
