#!/usr/bin/env python3
"""
Pre-Scan Node CLI Test
=======================
Test script to demonstrate scanning and fixing IaC files locally.

Usage:
    python test_cli.py scan <path>        # Scan files
    python test_cli.py fix <path>         # Scan and fix files
    python test_cli.py demo               # Run full demo with sample files

Requirements:
    pip install pyyaml
"""

import os
import sys
import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# ============================================================
# Colors for CLI output
# ============================================================

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('')  # Enable ANSI escape codes on Windows

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}[ERROR] {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.RESET}")

def print_finding(severity: str, title: str, file: str, line: int):
    color = Colors.RED if severity in ['HIGH', 'CRITICAL'] else Colors.YELLOW
    print(f"  {color}[{severity}]{Colors.RESET} {title}")
    print(f"           File: {file}:{line}")

# ============================================================
# Simple Scanner (no external dependencies)
# ============================================================

class SimpleFinding:
    def __init__(self, check_id: str, title: str, severity: str, 
                 file_path: str, line: int, pattern: str):
        self.check_id = check_id
        self.title = title
        self.severity = severity
        self.file_path = file_path
        self.line = line
        self.pattern = pattern

class SimpleScanner:
    """Simple regex-based scanner for demo purposes."""
    
    RULES = [
        {
            "id": "SG_WORLD_OPEN_SSH",
            "title": "Security Group allows SSH from 0.0.0.0/0",
            "severity": "HIGH",
            "pattern": r'remote_ip_prefix\s*=\s*"0\.0\.0\.0/0".*?port_range_min\s*=\s*22',
            "file_types": [".tf"]
        },
        {
            "id": "SG_WORLD_OPEN_RDP", 
            "title": "Security Group allows RDP from 0.0.0.0/0",
            "severity": "HIGH",
            "pattern": r'remote_ip_prefix\s*=\s*"0\.0\.0\.0/0".*?port_range_min\s*=\s*3389',
            "file_types": [".tf"]
        },
        {
            "id": "SG_WORLD_OPEN_ANY",
            "title": "Security Group allows traffic from 0.0.0.0/0",
            "severity": "MEDIUM",
            "pattern": r'remote_ip_prefix\s*=\s*"0\.0\.0\.0/0"',
            "file_types": [".tf"]
        },
        {
            "id": "SSH_PASSWORD_AUTH",
            "title": "SSH Password Authentication is enabled",
            "severity": "HIGH", 
            "pattern": r'PasswordAuthentication\s+yes',
            "file_types": [".yml", ".yaml", ".tf"]
        },
        {
            "id": "SSH_ROOT_LOGIN",
            "title": "SSH Root Login is permitted",
            "severity": "HIGH",
            "pattern": r'PermitRootLogin\s+yes',
            "file_types": [".yml", ".yaml", ".tf"]
        },
        {
            "id": "PORT_SECURITY_DISABLED",
            "title": "Port security is disabled",
            "severity": "HIGH",
            "pattern": r'port_security_enabled\s*=\s*false',
            "file_types": [".tf"]
        },
        {
            "id": "MISSING_TAGS",
            "title": "Resource missing required metadata/tags",
            "severity": "LOW",
            "pattern": r'resource\s+"openstack_compute_instance_v2".*?(?!metadata)',
            "file_types": [".tf"]
        },
        {
            "id": "YAML_TRAILING_SPACES",
            "title": "YAML file has trailing whitespace",
            "severity": "LOW",
            "pattern": r'[ \t]+$',
            "file_types": [".yml", ".yaml"]
        },
        {
            "id": "INSECURE_CIDR_SSH",
            "title": "SSH access open to wide CIDR (0.0.0.0/0)",
            "severity": "HIGH",
            "pattern": r'cidr\s*=\s*"0\.0\.0\.0/0".*?22',
            "file_types": [".tf"]
        },
    ]
    
    def scan(self, target_path: Path) -> List[SimpleFinding]:
        """Scan files for security issues."""
        findings = []
        
        if target_path.is_file():
            files = [target_path]
        else:
            files = list(target_path.rglob("*.tf")) + \
                   list(target_path.rglob("*.yml")) + \
                   list(target_path.rglob("*.yaml"))
        
        for file_path in files:
            if '.git' in str(file_path) or '__pycache__' in str(file_path):
                continue
                
            try:
                content = file_path.read_text(encoding='utf-8')
                file_findings = self._scan_content(file_path, content)
                findings.extend(file_findings)
            except Exception as e:
                print_warning(f"Could not read {file_path}: {e}")
        
        return findings
    
    def _scan_content(self, file_path: Path, content: str) -> List[SimpleFinding]:
        """Scan file content against rules."""
        findings = []
        
        for rule in self.RULES:
            # Check file type
            if not any(str(file_path).endswith(ft) for ft in rule["file_types"]):
                continue
            
            # Search for pattern
            matches = list(re.finditer(rule["pattern"], content, re.DOTALL | re.MULTILINE))
            
            for match in matches:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                
                finding = SimpleFinding(
                    check_id=rule["id"],
                    title=rule["title"],
                    severity=rule["severity"],
                    file_path=str(file_path),
                    line=line_num,
                    pattern=rule["pattern"]
                )
                findings.append(finding)
        
        return findings

# ============================================================
# Simple Fixer
# ============================================================

class SimpleFixer:
    """Simple regex-based fixer for demo purposes."""
    
    FIX_RULES = {
        "SG_WORLD_OPEN_SSH": {
            "pattern": r'(remote_ip_prefix\s*=\s*)"0\.0\.0\.0/0"',
            "replacement": r'\1"${var.admin_cidr}"',
            "description": "Replace 0.0.0.0/0 with admin_cidr variable"
        },
        "SG_WORLD_OPEN_RDP": {
            "pattern": r'(remote_ip_prefix\s*=\s*)"0\.0\.0\.0/0"',
            "replacement": r'\1"${var.admin_cidr}"',
            "description": "Replace 0.0.0.0/0 with admin_cidr variable"
        },
        "SG_WORLD_OPEN_ANY": {
            "pattern": r'(remote_ip_prefix\s*=\s*)"0\.0\.0\.0/0"',
            "replacement": r'\1"${var.admin_cidr}"',
            "description": "Replace 0.0.0.0/0 with admin_cidr variable"
        },
        "INSECURE_CIDR_SSH": {
            "pattern": r'(cidr\s*=\s*)"0\.0\.0\.0/0"',
            "replacement": r'\1"${var.admin_cidr}"',
            "description": "Replace 0.0.0.0/0 with admin_cidr variable"
        },
        "SSH_PASSWORD_AUTH": {
            "pattern": r'PasswordAuthentication\s+yes',
            "replacement": "PasswordAuthentication no",
            "description": "Disable password authentication"
        },
        "SSH_ROOT_LOGIN": {
            "pattern": r'PermitRootLogin\s+yes',
            "replacement": "PermitRootLogin no",
            "description": "Disable root login"
        },
        "PORT_SECURITY_DISABLED": {
            "pattern": r'port_security_enabled\s*=\s*false',
            "replacement": "port_security_enabled = true",
            "description": "Enable port security"
        },
        "YAML_TRAILING_SPACES": {
            "pattern": r'[ \t]+$',
            "replacement": "",
            "description": "Remove trailing whitespace"
        },
    }
    
    def fix(self, findings: List[SimpleFinding], dry_run: bool = False) -> Dict[str, List[str]]:
        """Fix findings and return results."""
        results = {
            "fixed": [],
            "skipped": [],
            "no_rule": []
        }
        
        # Group findings by file
        files_to_fix: Dict[str, List[SimpleFinding]] = {}
        for finding in findings:
            if finding.file_path not in files_to_fix:
                files_to_fix[finding.file_path] = []
            files_to_fix[finding.file_path].append(finding)
        
        for file_path, file_findings in files_to_fix.items():
            try:
                path = Path(file_path)
                content = path.read_text(encoding='utf-8')
                original_content = content
                
                for finding in file_findings:
                    if finding.check_id in self.FIX_RULES:
                        rule = self.FIX_RULES[finding.check_id]
                        new_content = re.sub(
                            rule["pattern"], 
                            rule["replacement"], 
                            content,
                            flags=re.MULTILINE
                        )
                        
                        if new_content != content:
                            content = new_content
                            results["fixed"].append(f"{finding.check_id} in {path.name}")
                        else:
                            results["skipped"].append(f"{finding.check_id} in {path.name}")
                    else:
                        results["no_rule"].append(f"{finding.check_id} in {path.name}")
                
                # Write fixed content
                if not dry_run and content != original_content:
                    # Create backup
                    backup_path = path.with_suffix(path.suffix + '.bak')
                    shutil.copy(path, backup_path)
                    
                    # Write fixed content
                    path.write_text(content, encoding='utf-8')
                    
            except Exception as e:
                print_error(f"Error fixing {file_path}: {e}")
        
        return results

# ============================================================
# Demo Functions
# ============================================================

def create_demo_files(demo_dir: Path):
    """Create sample files with security issues for demo."""
    
    demo_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Terraform file with issues
    tf_content = '''# Demo Terraform file with security issues
# This file intentionally contains misconfigurations for testing

# Security Group with SSH open to world (BAD!)
resource "openstack_networking_secgroup_v2" "demo_sg" {
  name        = "demo-insecure-sg"
  description = "Demo security group with issues"
}

#  SSH open to 0.0.0.0/0 - SECURITY ISSUE!
resource "openstack_networking_secgroup_rule_v2" "ssh_rule" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.demo_sg.id
}

#  RDP open to 0.0.0.0/0 - SECURITY ISSUE!
resource "openstack_networking_secgroup_rule_v2" "rdp_rule" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3389
  port_range_max    = 3389
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.demo_sg.id
}

#  Port security disabled - SECURITY ISSUE!
resource "openstack_networking_port_v2" "demo_port" {
  name               = "demo-port"
  network_id         = "some-network-id"
  admin_state_up     = true
  port_security_enabled = false
}

# Instance with the insecure security group
resource "openstack_compute_instance_v2" "demo_instance" {
  name            = "demo-instance"
  image_name      = "Ubuntu-22.04"
  flavor_name     = "m1.small"
  key_pair        = "my-keypair"
  security_groups = [openstack_networking_secgroup_v2.demo_sg.name]
}
'''
    
    tf_file = demo_dir / "insecure_demo.tf"
    tf_file.write_text(tf_content)
    print_info(f"Created: {tf_file}")
    
    # Create Ansible file with issues
    ansible_content = '''---
# Demo Ansible playbook with security issues
# This file intentionally contains misconfigurations for testing

- name: Configure Demo Server (INSECURE)
  hosts: all
  become: yes
  
  tasks:
    #  Enabling password auth - SECURITY ISSUE!
    - name: Configure SSH (INSECURE)
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^PasswordAuthentication'
        line: 'PasswordAuthentication yes'
      notify: Restart SSH

    #  Enabling root login - SECURITY ISSUE!    
    - name: Allow root login (INSECURE)
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: '^PermitRootLogin'
        line: 'PermitRootLogin yes'
      notify: Restart SSH

    - name: Install packages
      apt:
        name: 
          - nginx
          - curl
        state: present
        update_cache: yes   

  handlers:
    - name: Restart SSH
      service:
        name: sshd
        state: restarted
'''
    
    ansible_file = demo_dir / "insecure_demo.yml"
    ansible_file.write_text(ansible_content)
    print_info(f"Created: {ansible_file}")
    
    return [tf_file, ansible_file]

def run_demo():
    """Run full demo with sample files."""
    print_header("PRE-SCAN NODE DEMO")
    
    # Create demo directory
    demo_dir = Path(__file__).parent / "demo_test"
    
    print_info("Creating demo files with security issues...\n")
    create_demo_files(demo_dir)
    
    # Phase 1: Scan
    print_header("PHASE 1: SCANNING")
    scanner = SimpleScanner()
    findings = scanner.scan(demo_dir)
    
    if findings:
        print_error(f"Found {len(findings)} security issues:\n")
        for f in findings:
            print_finding(f.severity, f.title, Path(f.file_path).name, f.line)
    else:
        print_success("No issues found!")
        return
    
    # Ask to fix
    print("\n")
    print_warning("Do you want to auto-fix these issues? (y/n): ")
    response = input().strip().lower()
    
    if response == 'y':
        # Phase 2: Fix
        print_header("PHASE 2: AUTO-FIXING")
        fixer = SimpleFixer()
        results = fixer.fix(findings, dry_run=False)
        
        if results["fixed"]:
            print_success(f"Fixed {len(results['fixed'])} issues:")
            for fix in results["fixed"]:
                print(f"   {fix}")
        
        if results["no_rule"]:
            print_warning(f"\nNo fix rule for {len(results['no_rule'])} issues:")
            for skip in results["no_rule"]:
                print(f"    {skip}")
        
        # Phase 3: Verify
        print_header("PHASE 3: VERIFICATION SCAN")
        findings_after = scanner.scan(demo_dir)
        
        if findings_after:
            remaining = len([f for f in findings_after if f.severity in ['HIGH', 'CRITICAL']])
            if remaining > 0:
                print_warning(f"Still have {remaining} HIGH/CRITICAL issues")
            else:
                print_success("All HIGH/CRITICAL issues fixed!")
                print_info(f"{len(findings_after)} LOW severity issues remaining")
        else:
            print_success("All issues fixed! ")
        
        print("\n Backup files created with .bak extension")
        print(f" Fixed files in: {demo_dir}")
    else:
        print_info("Skipping auto-fix. You can run 'python test_cli.py fix demo_test' later.")
    
    print("\n")

def scan_path(path: str):
    """Scan specified path."""
    print_header("SCANNING FILES")
    
    target = Path(path)
    if not target.exists():
        print_error(f"Path not found: {path}")
        return
    
    print_info(f"Scanning: {target}\n")
    
    scanner = SimpleScanner()
    findings = scanner.scan(target)
    
    # Group by severity
    by_severity = {}
    for f in findings:
        if f.severity not in by_severity:
            by_severity[f.severity] = []
        by_severity[f.severity].append(f)
    
    # Print summary
    print(f"\n{Colors.BOLD} SCAN SUMMARY{Colors.RESET}")
    print("-" * 40)
    
    total = len(findings)
    critical = len(by_severity.get("CRITICAL", []))
    high = len(by_severity.get("HIGH", []))
    medium = len(by_severity.get("MEDIUM", []))
    low = len(by_severity.get("LOW", []))
    
    print(f"  Total Findings: {total}")
    print(f"  {Colors.RED}CRITICAL: {critical}{Colors.RESET}")
    print(f"  {Colors.RED}HIGH: {high}{Colors.RESET}")
    print(f"  {Colors.YELLOW}MEDIUM: {medium}{Colors.RESET}")
    print(f"  {Colors.BLUE}LOW: {low}{Colors.RESET}")
    print("-" * 40)
    
    if findings:
        print(f"\n{Colors.BOLD} DETAILED FINDINGS{Colors.RESET}\n")
        for f in sorted(findings, key=lambda x: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].index(x.severity) if x.severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] else 4):
            print_finding(f.severity, f.title, Path(f.file_path).name, f.line)
            print()

def fix_path(path: str, dry_run: bool = False):
    """Scan and fix specified path."""
    print_header("SCAN AND FIX")
    
    target = Path(path)
    if not target.exists():
        print_error(f"Path not found: {path}")
        return
    
    # Scan
    print_info(f"Scanning: {target}\n")
    scanner = SimpleScanner()
    findings = scanner.scan(target)
    
    if not findings:
        print_success("No issues found!")
        return
    
    print_error(f"Found {len(findings)} issues\n")
    for f in findings:
        print_finding(f.severity, f.title, Path(f.file_path).name, f.line)
    
    # Fix
    print_header("APPLYING FIXES")
    
    if dry_run:
        print_info("DRY RUN MODE - no files will be modified\n")
    
    fixer = SimpleFixer()
    results = fixer.fix(findings, dry_run=dry_run)
    
    print(f"\n{Colors.BOLD} FIX SUMMARY{Colors.RESET}")
    print("-" * 40)
    print(f"  {Colors.GREEN}Fixed: {len(results['fixed'])}{Colors.RESET}")
    print(f"  {Colors.YELLOW}Skipped: {len(results['skipped'])}{Colors.RESET}")
    print(f"  {Colors.BLUE}No Rule: {len(results['no_rule'])}{Colors.RESET}")
    print("-" * 40)
    
    if results["fixed"] and not dry_run:
        print(f"\n{Colors.GREEN} Fixes applied! Backup files created with .bak extension{Colors.RESET}")
        
        # Re-scan
        print(f"\n{Colors.BOLD} VERIFICATION SCAN{Colors.RESET}\n")
        findings_after = scanner.scan(target)
        
        fixed_count = len(findings) - len(findings_after)
        print_success(f"Reduced from {len(findings)} to {len(findings_after)} issues ({fixed_count} fixed)")

# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Pre-Scan Node CLI Test Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_cli.py demo              # Run interactive demo
  python test_cli.py scan ./terraform  # Scan terraform directory
  python test_cli.py fix ./terraform   # Scan and fix issues
  python test_cli.py fix ./terraform --dry-run  # Preview fixes
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Demo command
    subparsers.add_parser("demo", help="Run interactive demo with sample files")
    
    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan files for security issues")
    scan_parser.add_argument("path", help="Path to scan")
    
    # Fix command
    fix_parser = subparsers.add_parser("fix", help="Scan and fix security issues")
    fix_parser.add_argument("path", help="Path to fix")
    fix_parser.add_argument("--dry-run", action="store_true", help="Preview fixes without applying")
    
    args = parser.parse_args()
    
    if args.command == "demo":
        run_demo()
    elif args.command == "scan":
        scan_path(args.path)
    elif args.command == "fix":
        fix_path(args.path, args.dry_run)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
