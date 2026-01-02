"""
IaC Scanner Service
====================
Scans Terraform and Ansible files for security misconfigurations.
Supports multiple scanning tools: Checkov, Trivy, ansible-lint, yamllint.
"""

import os
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import yaml

logger = logging.getLogger(__name__)


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class Finding:
    """Represents a security finding from scanning."""
    id: str
    scanner: str
    check_id: str
    title: str
    description: str
    severity: Severity
    file_path: str
    line_start: int
    line_end: int
    resource: Optional[str] = None
    code_snippet: Optional[str] = None
    fix_available: bool = False
    fix_runbook_id: Optional[str] = None
    guideline: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "scanner": self.scanner,
            "check_id": self.check_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "resource": self.resource,
            "code_snippet": self.code_snippet,
            "fix_available": self.fix_available,
            "fix_runbook_id": self.fix_runbook_id,
            "guideline": self.guideline,
        }


@dataclass
class ScanResult:
    """Result of a scan operation."""
    scan_id: str
    scanner: str
    target_path: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"  # running, passed, failed, error
    findings: List[Finding] = field(default_factory=list)
    exit_code: int = 0
    raw_output: str = ""
    error_message: Optional[str] = None
    
    @property
    def finding_count(self) -> int:
        return len(self.findings)
    
    @property
    def critical_count(self) -> int:
        return len([f for f in self.findings if f.severity == Severity.CRITICAL])
    
    @property
    def high_count(self) -> int:
        return len([f for f in self.findings if f.severity == Severity.HIGH])
    
    def to_dict(self) -> Dict:
        return {
            "scan_id": self.scan_id,
            "scanner": self.scanner,
            "target_path": self.target_path,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "finding_count": self.finding_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "findings": [f.to_dict() for f in self.findings],
            "exit_code": self.exit_code,
            "error_message": self.error_message,
        }


class BaseScanner(ABC):
    """Base class for IaC scanners."""
    
    name: str = "base"
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._finding_counter = 0
    
    @abstractmethod
    def scan(self, target_path: Path) -> ScanResult:
        """Perform scan on target path."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if scanner is installed and available."""
        pass
    
    def _generate_finding_id(self) -> str:
        self._finding_counter += 1
        return f"{self.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._finding_counter}"
    
    def _run_command(self, cmd: List[str], cwd: Path = None) -> tuple:
        """Run a command and return (exit_code, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class CheckovScanner(BaseScanner):
    """Checkov IaC scanner for Terraform and Ansible."""
    
    name = "checkov"
    
    def is_available(self) -> bool:
        code, _, _ = self._run_command(["checkov", "--version"])
        return code == 0
    
    def scan(self, target_path: Path) -> ScanResult:
        scan_id = f"checkov_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = ScanResult(
            scan_id=scan_id,
            scanner=self.name,
            target_path=str(target_path),
            started_at=datetime.now()
        )
        
        # Build command
        cmd = [
            "checkov",
            "-d", str(target_path),
            "--output", "json",
            "--quiet"
        ]
        
        # Add severity filter
        severity = self.config.get("severity", ["HIGH", "CRITICAL"])
        if severity:
            cmd.extend(["--check-severity", ",".join(severity)])
        
        # Add skip checks
        skip_checks = self.config.get("skip_checks", [])
        for check in skip_checks:
            cmd.extend(["--skip-check", check])
        
        exit_code, stdout, stderr = self._run_command(cmd)
        result.exit_code = exit_code
        result.raw_output = stdout
        
        if exit_code == -1:
            result.status = "error"
            result.error_message = stderr
        else:
            try:
                findings = self._parse_output(stdout, target_path)
                result.findings = findings
                result.status = "passed" if exit_code == 0 else "failed"
            except Exception as e:
                result.status = "error"
                result.error_message = f"Failed to parse output: {e}"
        
        result.completed_at = datetime.now()
        return result
    
    def _parse_output(self, output: str, target_path: Path) -> List[Finding]:
        """Parse Checkov JSON output into findings."""
        findings = []
        
        if not output.strip():
            return findings
        
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            logger.warning("Could not parse Checkov output as JSON")
            return findings
        
        # Handle both single result and list of results
        results_list = data if isinstance(data, list) else [data]
        
        for result in results_list:
            failed_checks = result.get("results", {}).get("failed_checks", [])
            
            for check in failed_checks:
                severity = self._map_severity(check.get("severity", "MEDIUM"))
                
                finding = Finding(
                    id=self._generate_finding_id(),
                    scanner=self.name,
                    check_id=check.get("check_id", ""),
                    title=check.get("check_id", ""),
                    description=check.get("check_result", {}).get("evaluated_keys", [""])[0] if check.get("check_result") else "",
                    severity=severity,
                    file_path=check.get("file_path", ""),
                    line_start=check.get("file_line_range", [0, 0])[0],
                    line_end=check.get("file_line_range", [0, 0])[1],
                    resource=check.get("resource", ""),
                    guideline=check.get("guideline", ""),
                )
                findings.append(finding)
        
        return findings
    
    def _map_severity(self, severity: str) -> Severity:
        mapping = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
            "INFO": Severity.INFO,
        }
        return mapping.get(severity.upper(), Severity.MEDIUM)


class TrivyScanner(BaseScanner):
    """Trivy IaC scanner."""
    
    name = "trivy"
    
    def is_available(self) -> bool:
        code, _, _ = self._run_command(["docker", "version"])
        return code == 0
    
    def scan(self, target_path: Path) -> ScanResult:
        scan_id = f"trivy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = ScanResult(
            scan_id=scan_id,
            scanner=self.name,
            target_path=str(target_path),
            started_at=datetime.now()
        )
        
        # Run Trivy via Docker
        severity = self.config.get("severity", ["HIGH", "CRITICAL"])
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{target_path}:/work",
            "-w", "/work",
            "aquasec/trivy:latest",
            "config",
            "--format", "json",
            "--severity", ",".join(severity),
            "."
        ]
        
        exit_code, stdout, stderr = self._run_command(cmd)
        result.exit_code = exit_code
        result.raw_output = stdout
        
        if exit_code == -1:
            result.status = "error"
            result.error_message = stderr
        else:
            try:
                findings = self._parse_output(stdout)
                result.findings = findings
                result.status = "passed" if len(findings) == 0 else "failed"
            except Exception as e:
                result.status = "error"
                result.error_message = f"Failed to parse output: {e}"
        
        result.completed_at = datetime.now()
        return result
    
    def _parse_output(self, output: str) -> List[Finding]:
        """Parse Trivy JSON output."""
        findings = []
        
        if not output.strip():
            return findings
        
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return findings
        
        results = data.get("Results", [])
        for result in results:
            misconfigs = result.get("Misconfigurations", [])
            for mc in misconfigs:
                severity = Severity[mc.get("Severity", "MEDIUM").upper()]
                finding = Finding(
                    id=self._generate_finding_id(),
                    scanner=self.name,
                    check_id=mc.get("ID", ""),
                    title=mc.get("Title", ""),
                    description=mc.get("Description", ""),
                    severity=severity,
                    file_path=result.get("Target", ""),
                    line_start=mc.get("CauseMetadata", {}).get("StartLine", 0),
                    line_end=mc.get("CauseMetadata", {}).get("EndLine", 0),
                    resource=mc.get("CauseMetadata", {}).get("Resource", ""),
                    code_snippet=mc.get("CauseMetadata", {}).get("Code", {}).get("Lines", []),
                )
                findings.append(finding)
        
        return findings


class AnsibleLintScanner(BaseScanner):
    """Ansible-lint scanner."""
    
    name = "ansible-lint"
    
    def is_available(self) -> bool:
        code, _, _ = self._run_command(["docker", "version"])
        return code == 0
    
    def scan(self, target_path: Path) -> ScanResult:
        scan_id = f"ansible-lint_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = ScanResult(
            scan_id=scan_id,
            scanner=self.name,
            target_path=str(target_path),
            started_at=datetime.now()
        )
        
        # Find YAML files
        yaml_files = list(target_path.glob("**/*.yml")) + list(target_path.glob("**/*.yaml"))
        if not yaml_files:
            result.status = "passed"
            result.completed_at = datetime.now()
            return result
        
        # Run ansible-lint via Docker
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{target_path}:/work",
            "-w", "/work",
            "cytopia/ansible-lint:latest",
            "ansible-lint",
            "--format", "json",
            "-p"
        ] + [str(f.relative_to(target_path)) for f in yaml_files[:10]]  # Limit files
        
        exit_code, stdout, stderr = self._run_command(cmd)
        result.exit_code = exit_code
        result.raw_output = stdout
        
        if exit_code == -1:
            result.status = "error"
            result.error_message = stderr
        else:
            try:
                findings = self._parse_output(stdout)
                result.findings = findings
                result.status = "passed" if len(findings) == 0 else "failed"
            except Exception as e:
                result.status = "error"
                result.error_message = f"Failed to parse output: {e}"
        
        result.completed_at = datetime.now()
        return result
    
    def _parse_output(self, output: str) -> List[Finding]:
        """Parse ansible-lint output."""
        findings = []
        
        try:
            data = json.loads(output)
            for item in data:
                severity = self._map_severity(item.get("severity", "warning"))
                finding = Finding(
                    id=self._generate_finding_id(),
                    scanner=self.name,
                    check_id=item.get("rule", {}).get("id", ""),
                    title=item.get("rule", {}).get("shortdesc", ""),
                    description=item.get("message", ""),
                    severity=severity,
                    file_path=item.get("filename", ""),
                    line_start=item.get("linenumber", 0),
                    line_end=item.get("linenumber", 0),
                )
                findings.append(finding)
        except json.JSONDecodeError:
            # Parse text output
            for line in output.split("\n"):
                if ": " in line and line.strip():
                    parts = line.split(":")
                    if len(parts) >= 3:
                        finding = Finding(
                            id=self._generate_finding_id(),
                            scanner=self.name,
                            check_id="ansible-lint",
                            title=parts[-1].strip() if parts else "",
                            description=line,
                            severity=Severity.MEDIUM,
                            file_path=parts[0] if parts else "",
                            line_start=int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                            line_end=0,
                        )
                        findings.append(finding)
        
        return findings
    
    def _map_severity(self, severity: str) -> Severity:
        mapping = {
            "error": Severity.HIGH,
            "warning": Severity.MEDIUM,
            "info": Severity.LOW,
        }
        return mapping.get(severity.lower(), Severity.MEDIUM)


class YamllintScanner(BaseScanner):
    """Yamllint scanner for YAML files."""
    
    name = "yamllint"
    
    def is_available(self) -> bool:
        code, _, _ = self._run_command(["yamllint", "--version"])
        return code == 0
    
    def scan(self, target_path: Path) -> ScanResult:
        scan_id = f"yamllint_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = ScanResult(
            scan_id=scan_id,
            scanner=self.name,
            target_path=str(target_path),
            started_at=datetime.now()
        )
        
        cmd = ["yamllint", "-f", "parsable", str(target_path)]
        
        exit_code, stdout, stderr = self._run_command(cmd)
        result.exit_code = exit_code
        result.raw_output = stdout
        
        if exit_code == -1:
            result.status = "error"
            result.error_message = stderr
        else:
            findings = self._parse_output(stdout)
            result.findings = findings
            result.status = "passed" if len(findings) == 0 else "failed"
        
        result.completed_at = datetime.now()
        return result
    
    def _parse_output(self, output: str) -> List[Finding]:
        """Parse yamllint parsable output."""
        findings = []
        
        for line in output.split("\n"):
            if not line.strip():
                continue
            
            # Format: file:line:col: [level] message (rule)
            parts = line.split(":")
            if len(parts) >= 4:
                file_path = parts[0]
                line_num = int(parts[1]) if parts[1].isdigit() else 0
                
                # Extract level and message
                rest = ":".join(parts[3:]).strip()
                level = "warning"
                if rest.startswith("[error]"):
                    level = "error"
                    rest = rest[7:].strip()
                elif rest.startswith("[warning]"):
                    rest = rest[9:].strip()
                
                severity = Severity.HIGH if level == "error" else Severity.LOW
                
                finding = Finding(
                    id=self._generate_finding_id(),
                    scanner=self.name,
                    check_id="yamllint",
                    title="YAML formatting issue",
                    description=rest,
                    severity=severity,
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                )
                findings.append(finding)
        
        return findings


class IaCScanner:
    """
    Main IaC Scanner that orchestrates multiple scanning tools.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.scanners: Dict[str, BaseScanner] = {}
        self._init_scanners()
    
    def _init_scanners(self):
        """Initialize available scanners."""
        scanner_classes = [
            CheckovScanner,
            TrivyScanner,
            AnsibleLintScanner,
            YamllintScanner,
        ]
        
        enabled_scanners = self.config.get("enabled", [])
        
        for scanner_class in scanner_classes:
            scanner_name = scanner_class.name
            
            # Skip if not in enabled list (if list is provided)
            if enabled_scanners and scanner_name not in enabled_scanners:
                continue
            
            scanner_config = self.config.get(scanner_name, {})
            scanner = scanner_class(scanner_config)
            
            if scanner.is_available():
                self.scanners[scanner_name] = scanner
                logger.info(f"Scanner {scanner_name} is available")
            else:
                logger.warning(f"Scanner {scanner_name} is not available")
    
    def scan(self, target_path: Path, scanners: List[str] = None) -> Dict[str, ScanResult]:
        """
        Run all configured scanners on the target path.
        
        Args:
            target_path: Path to scan
            scanners: List of specific scanners to run (optional)
        
        Returns:
            Dictionary of scanner_name -> ScanResult
        """
        results = {}
        
        scanners_to_run = scanners or list(self.scanners.keys())
        
        for scanner_name in scanners_to_run:
            if scanner_name not in self.scanners:
                logger.warning(f"Scanner {scanner_name} not available")
                continue
            
            logger.info(f"Running {scanner_name} on {target_path}")
            scanner = self.scanners[scanner_name]
            
            try:
                result = scanner.scan(target_path)
                results[scanner_name] = result
                logger.info(f"{scanner_name} completed: {result.status}, {result.finding_count} findings")
            except Exception as e:
                logger.error(f"Error running {scanner_name}: {e}")
                results[scanner_name] = ScanResult(
                    scan_id=f"{scanner_name}_error",
                    scanner=scanner_name,
                    target_path=str(target_path),
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    status="error",
                    error_message=str(e)
                )
        
        return results
    
    def get_all_findings(self, results: Dict[str, ScanResult]) -> List[Finding]:
        """Get all findings from scan results."""
        all_findings = []
        for result in results.values():
            all_findings.extend(result.findings)
        return all_findings
    
    def get_available_scanners(self) -> List[str]:
        """Get list of available scanners."""
        return list(self.scanners.keys())


def create_scanner_from_config(config_path: str) -> IaCScanner:
    """Create IaCScanner from YAML config file."""
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    scanner_config = config_data.get('scanners', {})
    return IaCScanner(scanner_config)


if __name__ == "__main__":
    # Test the scanner
    logging.basicConfig(level=logging.INFO)
    
    scanner = IaCScanner({
        "enabled": ["checkov", "yamllint"],
        "checkov": {
            "severity": ["HIGH", "CRITICAL"]
        }
    })
    
    print("Available scanners:", scanner.get_available_scanners())
    
    # Test scan
    test_path = Path("./test_terraform")
    if test_path.exists():
        results = scanner.scan(test_path)
        for name, result in results.items():
            print(f"\n{name}: {result.status}")
            print(f"  Findings: {result.finding_count}")
            for finding in result.findings[:5]:
                print(f"    - [{finding.severity.value}] {finding.title}")
