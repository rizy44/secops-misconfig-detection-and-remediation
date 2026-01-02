"""
Pre-Scan Node - Main Application
=================================
Automated IaC security scanning and remediation node.

This application watches for new Terraform/Ansible files, scans them for
security misconfigurations, automatically fixes issues using predefined
runbooks, and deploys validated infrastructure.
"""

import os
import sys
import logging
import threading
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yaml
import uvicorn

# Add services to path
sys.path.insert(0, str(Path(__file__).parent))

from services.watcher import FileWatcher, WatcherConfig, WatchedFile
from services.scanner import IaCScanner, ScanResult, Finding
from services.fixer import AutoFixer, FixBatch
from services.deployer import Deployer, Deployment

# ============================================================
# Configuration
# ============================================================

def load_config(config_path: str = None) -> Dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = os.environ.get(
            "PRESCAN_CONFIG",
            "/app/config/prescan_config.yml"
        )
    
    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    # Return default config
    return {
        "node": {"name": "prescan-node", "log_level": "INFO"},
        "watcher": {"watch_dir": "/deploy/in", "poll_interval": 5},
        "scanners": {"enabled": ["checkov", "yamllint"]},
        "auto_fix": {"enabled": True},
        "deploy": {"enabled": True},
        "api": {"host": "0.0.0.0", "port": 8001}
    }


# ============================================================
# Logging
# ============================================================

def setup_logging(config: Dict):
    """Setup logging configuration."""
    log_level = config.get("node", {}).get("log_level", "INFO")
    log_file = config.get("node", {}).get("log_file", None)
    
    handlers = [logging.StreamHandler()]
    
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )


# ============================================================
# Core Application Class
# ============================================================

class PreScanNode:
    """
    Main Pre-Scan Node application.
    
    Orchestrates:
    - File watching for new deployments
    - IaC security scanning
    - Automatic fixing via runbooks
    - Deployment of validated infrastructure
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger("PreScanNode")
        
        # Initialize components
        self._init_watcher()
        self._init_scanner()
        self._init_fixer()
        self._init_deployer()
        
        # State tracking
        self.scan_history: List[Dict] = []
        self.fix_history: List[FixBatch] = []
        self.deploy_history: List[Deployment] = []
        
        # Status
        self.status = "initialized"
        self.started_at: Optional[datetime] = None
        
        self.logger.info("Pre-Scan Node initialized")
    
    def _init_watcher(self):
        """Initialize file watcher."""
        watcher_config = self.config.get("watcher", {})
        
        config = WatcherConfig(
            watch_dir=Path(watcher_config.get("watch_dir", "/deploy/in")),
            poll_interval=watcher_config.get("poll_interval", 5),
            patterns=watcher_config.get("patterns", {}),
            ignore_patterns=watcher_config.get("ignore", [])
        )
        
        self.watcher = FileWatcher(config)
        
        # Register callbacks
        self.watcher.on_batch_ready(self._on_batch_ready)
        
        self.logger.info(f"Watcher configured for: {config.watch_dir}")
    
    def _init_scanner(self):
        """Initialize IaC scanner."""
        scanner_config = self.config.get("scanners", {})
        self.scanner = IaCScanner(scanner_config)
        
        available = self.scanner.get_available_scanners()
        self.logger.info(f"Available scanners: {available}")
    
    def _init_fixer(self):
        """Initialize auto-fixer."""
        fix_config = self.config.get("auto_fix", {})
        catalog_path = Path(fix_config.get(
            "runbook_catalog",
            "/app/runbooks/catalog.yml"
        ))
        
        self.fixer = AutoFixer(fix_config, catalog_path)
        
        # Set default variables
        self.fixer.set_variables({
            "admin_cidr": os.environ.get("ADMIN_CIDR", "10.0.0.0/8"),
            "internal_cidr": os.environ.get("INTERNAL_CIDR", "10.10.50.0/24"),
        })
        
        self.logger.info(f"Auto-fixer enabled: {self.fixer.enabled}")
    
    def _init_deployer(self):
        """Initialize deployer."""
        deploy_config = self.config.get("deploy", {})
        self.deployer = Deployer(deploy_config)
        
        self.logger.info(f"Deployer enabled: {self.deployer.enabled}")
    
    def start(self):
        """Start the Pre-Scan Node."""
        self.logger.info("Starting Pre-Scan Node...")
        
        self.status = "running"
        self.started_at = datetime.now()
        
        # Create watch directory if needed
        watch_dir = self.watcher.watch_dir
        if not watch_dir.exists():
            watch_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created watch directory: {watch_dir}")
        
        # Start file watcher
        self.watcher.start()
        
        self.logger.info("Pre-Scan Node started successfully")
    
    def stop(self):
        """Stop the Pre-Scan Node."""
        self.logger.info("Stopping Pre-Scan Node...")
        
        self.watcher.stop()
        self.status = "stopped"
        
        self.logger.info("Pre-Scan Node stopped")
    
    def _on_batch_ready(self, files: List[WatchedFile]):
        """Handle batch of files ready for processing."""
        self.logger.info(f"Processing batch of {len(files)} files")
        
        if not files:
            return
        
        # Determine target path (common parent)
        target_path = files[0].path.parent
        
        # Run the scan-fix-deploy pipeline
        self.process_deployment(target_path)
    
    def process_deployment(self, target_path: Path) -> Dict:
        """
        Process a deployment directory through the full pipeline:
        1. Scan for security issues
        2. Auto-fix issues using runbooks
        3. Re-scan to verify fixes
        4. Deploy if clean
        
        Args:
            target_path: Path to the deployment files
        
        Returns:
            Pipeline results dictionary
        """
        pipeline_id = f"pipeline_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        results = {
            "id": pipeline_id,
            "target_path": str(target_path),
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "scan_results": {},
            "findings_count": 0,
            "fix_batch": None,
            "verification_results": {},
            "deployment": None,
        }
        
        try:
            # Phase 1: Initial Scan
            self.logger.info(f"Phase 1: Scanning {target_path}")
            scan_results = self.scanner.scan(target_path)
            results["scan_results"] = {
                name: result.to_dict() for name, result in scan_results.items()
            }
            
            # Collect all findings
            all_findings = self.scanner.get_all_findings(scan_results)
            results["findings_count"] = len(all_findings)
            
            self.logger.info(f"Found {len(all_findings)} security issues")
            
            # Phase 2: Auto-Fix
            if all_findings and self.fixer.enabled:
                self.logger.info("Phase 2: Applying automatic fixes")
                fix_batch = self.fixer.fix(all_findings, target_path)
                results["fix_batch"] = fix_batch.to_dict()
                self.fix_history.append(fix_batch)
                
                self.logger.info(
                    f"Applied {fix_batch.successful_actions}/{fix_batch.total_actions} fixes"
                )
                
                # Phase 3: Verification Scan
                if fix_batch.successful_actions > 0:
                    self.logger.info("Phase 3: Verification scan")
                    verify_results = self.scanner.scan(target_path)
                    results["verification_results"] = {
                        name: result.to_dict() for name, result in verify_results.items()
                    }
                    
                    remaining_findings = self.scanner.get_all_findings(verify_results)
                    high_critical = [
                        f for f in remaining_findings 
                        if f.severity in [Severity.HIGH, Severity.CRITICAL]
                    ]
                    
                    results["remaining_findings"] = len(remaining_findings)
                    results["remaining_high_critical"] = len(high_critical)
            
            # Phase 4: Deploy
            if self.deployer.enabled:
                # Check if safe to deploy
                remaining = results.get("remaining_findings", results["findings_count"])
                
                if remaining == 0:
                    self.logger.info("Phase 4: Deploying validated infrastructure")
                    deployment = self.deployer.deploy(target_path)
                    results["deployment"] = deployment.to_dict()
                    self.deploy_history.append(deployment)
                else:
                    self.logger.warning(
                        f"Skipping deployment: {remaining} findings remaining"
                    )
                    results["deployment_skipped"] = f"{remaining} findings remaining"
            
            results["status"] = "completed"
            results["completed_at"] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.error(f"Pipeline error: {e}")
            results["status"] = "failed"
            results["error"] = str(e)
        
        self.scan_history.append(results)
        return results
    
    def get_status(self) -> Dict:
        """Get current node status."""
        return {
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "watch_dir": str(self.watcher.watch_dir),
            "available_scanners": self.scanner.get_available_scanners(),
            "auto_fix_enabled": self.fixer.enabled,
            "deploy_enabled": self.deployer.enabled,
            "total_scans": len(self.scan_history),
            "total_fixes": len(self.fix_history),
            "total_deployments": len(self.deploy_history),
        }


# ============================================================
# FastAPI Application
# ============================================================

# Global node instance
node: Optional[PreScanNode] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global node
    
    # Startup
    config = load_config()
    setup_logging(config)
    
    node = PreScanNode(config)
    node.start()
    
    yield
    
    # Shutdown
    if node:
        node.stop()


app = FastAPI(
    title="Pre-Scan Node API",
    description="Automated IaC security scanning and remediation",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API Models
# ============================================================

class ScanRequest(BaseModel):
    path: str


class DeployRequest(BaseModel):
    path: str
    terraform: bool = True
    ansible: bool = True


# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/status")
async def get_status():
    """Get node status."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    return node.get_status()


@app.get("/api/scans")
async def list_scans():
    """List all scan results."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    return {"scans": node.scan_history}


@app.get("/api/scans/{scan_id}")
async def get_scan(scan_id: str):
    """Get specific scan result."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    for scan in node.scan_history:
        if scan.get("id") == scan_id:
            return scan
    
    raise HTTPException(status_code=404, detail="Scan not found")


@app.post("/api/scans")
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Trigger a new scan."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    target_path = Path(request.path)
    if not target_path.exists():
        raise HTTPException(status_code=400, detail="Path not found")
    
    # Run scan in background
    background_tasks.add_task(node.process_deployment, target_path)
    
    return {"message": "Scan started", "path": str(target_path)}


@app.get("/api/fixes")
async def list_fixes():
    """List all fix batches."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    return {"fixes": [f.to_dict() for f in node.fix_history]}


@app.get("/api/fixes/{fix_id}")
async def get_fix(fix_id: str):
    """Get specific fix batch."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    for fix in node.fix_history:
        if fix.id == fix_id:
            return fix.to_dict()
    
    raise HTTPException(status_code=404, detail="Fix batch not found")


@app.post("/api/fixes/{fix_id}/rollback")
async def rollback_fix(fix_id: str):
    """Rollback a fix batch."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    success = node.fixer.rollback(fix_id)
    if success:
        return {"message": "Rollback successful", "fix_id": fix_id}
    else:
        raise HTTPException(status_code=400, detail="Rollback failed")


@app.get("/api/deployments")
async def list_deployments():
    """List all deployments."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    return {"deployments": [d.to_dict() for d in node.deploy_history]}


@app.get("/api/deployments/{deploy_id}")
async def get_deployment(deploy_id: str):
    """Get specific deployment."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    for deploy in node.deploy_history:
        if deploy.id == deploy_id:
            return deploy.to_dict()
    
    raise HTTPException(status_code=404, detail="Deployment not found")


@app.post("/api/deployments")
async def trigger_deployment(request: DeployRequest, background_tasks: BackgroundTasks):
    """Trigger a new deployment."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    target_path = Path(request.path)
    if not target_path.exists():
        raise HTTPException(status_code=400, detail="Path not found")
    
    # Run deployment in background
    background_tasks.add_task(
        node.deployer.deploy,
        target_path,
        request.terraform,
        request.ansible
    )
    
    return {"message": "Deployment started", "path": str(target_path)}


@app.get("/api/files")
async def list_watched_files():
    """List currently watched files."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    files = node.watcher.get_files()
    return {
        "files": [
            {
                "path": str(f.path),
                "type": f.file_type.value,
                "scan_status": f.scan_status,
                "fix_status": f.fix_status,
                "last_modified": f.last_modified.isoformat(),
            }
            for f in files.values()
        ]
    }


@app.get("/api/runbooks")
async def list_runbooks():
    """List available runbooks."""
    if not node:
        raise HTTPException(status_code=503, detail="Node not initialized")
    
    runbooks = []
    for rb_id, rb in node.fixer.catalog.runbooks.items():
        runbooks.append({
            "id": rb_id,
            "name": rb.name,
            "description": rb.description,
            "severity": rb.severity,
            "auto_approve": rb.auto_approve,
        })
    
    return {"runbooks": runbooks}


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """Main entry point."""
    config = load_config()
    setup_logging(config)
    
    api_config = config.get("api", {})
    host = api_config.get("host", "0.0.0.0")
    port = api_config.get("port", 8001)
    workers = api_config.get("workers", 1)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=False
    )


if __name__ == "__main__":
    main()
