"""
OS Baseline Scanner

Scans OS-level security configurations (SSH, firewall, etc.)
Uses Ansible ad-hoc commands for remote checks.
"""

import os
import subprocess
import logging
from typing import List, Dict, Optional

log = logging.getLogger("secops")


def scan_os_baseline(conn, inventory_path: Optional[str] = None, timeout: int = 10) -> List[Dict]:
    """
    Scan OS baseline security configurations
    
    Args:
        conn: OpenStack connection
        inventory_path: Path to Ansible inventory file
        timeout: Command timeout in seconds
        
    Returns:
        List of findings
    """
    findings = []
    
    if not inventory_path or not os.path.exists(inventory_path):
        log.warning(f"Ansible inventory not found: {inventory_path}, skipping OS baseline scan")
        return findings
    
    try:
        # Get all servers with IPs
        for server in conn.compute.servers(details=True):
            addresses = server.addresses or {}
            
            # Prefer floating IP, fallback to fixed IP
            target_ip = None
            for network_name, addr_list in addresses.items():
                for addr in addr_list:
                    if addr.get("OS-EXT-IPS:type") == "floating":
                        target_ip = addr.get("addr")
                        break
                    elif not target_ip:
                        target_ip = addr.get("addr")
                if target_ip:
                    break
            
            if not target_ip:
                continue
            
            # Find hostname in inventory (simplified: match by IP)
            # In production, you'd want better matching logic
            hostname = server.name
            
            # Check SSH configuration
            ssh_findings = _check_ssh_config(inventory_path, hostname, target_ip, timeout)
            findings.extend(ssh_findings)
            
            # Check firewall
            firewall_findings = _check_firewall(inventory_path, hostname, target_ip, timeout)
            findings.extend(firewall_findings)
            
    except Exception as e:
        log.exception(f"Error scanning OS baseline: {e}")
    
    return findings


def _check_ssh_config(inventory_path: str, hostname: str, target_ip: str, timeout: int) -> List[Dict]:
    """Check SSH configuration"""
    findings = []
    
    # Check PasswordAuthentication
    try:
        result = subprocess.run(
            [
                "ansible", hostname,
                "-i", inventory_path,
                "-m", "shell",
                "-a", "grep -E '^PasswordAuthentication|^#PasswordAuthentication' /etc/ssh/sshd_config | tail -1",
                "--timeout", str(timeout)
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0 and "PasswordAuthentication yes" in result.stdout:
            findings.append({
                "type": "OS_SSH_PASSWORD_AUTH_ENABLED",
                "severity": "MEDIUM",
                "resource_id": target_ip,
                "summary": f"SSH password authentication enabled on {hostname}",
                "details_json": {
                    "hostname": hostname,
                    "ip": target_ip,
                    "check": "PasswordAuthentication"
                }
            })
    except subprocess.TimeoutExpired:
        log.warning(f"SSH config check timeout for {hostname}")
    except Exception as e:
        log.debug(f"SSH config check failed for {hostname}: {e}")
    
    # Check PermitRootLogin
    try:
        result = subprocess.run(
            [
                "ansible", hostname,
                "-i", inventory_path,
                "-m", "shell",
                "-a", "grep -E '^PermitRootLogin|^#PermitRootLogin' /etc/ssh/sshd_config | tail -1",
                "--timeout", str(timeout)
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0 and "PermitRootLogin yes" in result.stdout:
            findings.append({
                "type": "OS_SSH_ROOT_LOGIN_ENABLED",
                "severity": "HIGH",
                "resource_id": target_ip,
                "summary": f"SSH root login enabled on {hostname}",
                "details_json": {
                    "hostname": hostname,
                    "ip": target_ip,
                    "check": "PermitRootLogin"
                }
            })
    except subprocess.TimeoutExpired:
        log.warning(f"SSH root login check timeout for {hostname}")
    except Exception as e:
        log.debug(f"SSH root login check failed for {hostname}: {e}")
    
    return findings


def _check_firewall(inventory_path: str, hostname: str, target_ip: str, timeout: int) -> List[Dict]:
    """Check firewall status"""
    findings = []
    
    # Check ufw (Ubuntu/Debian)
    try:
        result = subprocess.run(
            [
                "ansible", hostname,
                "-i", inventory_path,
                "-m", "shell",
                "-a", "ufw status | grep -i 'Status: active' || echo 'inactive'",
                "--timeout", str(timeout)
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0 and "inactive" in result.stdout.lower():
            # Also check firewalld (RHEL/CentOS)
            result2 = subprocess.run(
                [
                    "ansible", hostname,
                    "-i", inventory_path,
                    "-m", "shell",
                    "-a", "systemctl is-active firewalld || echo 'inactive'",
                    "--timeout", str(timeout)
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 2
            )
            
            if "inactive" in result2.stdout.lower():
                findings.append({
                    "type": "OS_FIREWALL_DISABLED",
                    "severity": "MEDIUM",
                    "resource_id": target_ip,
                    "summary": f"Firewall not running on {hostname}",
                    "details_json": {
                        "hostname": hostname,
                        "ip": target_ip,
                        "check": "firewall"
                    }
                })
    except subprocess.TimeoutExpired:
        log.warning(f"Firewall check timeout for {hostname}")
    except Exception as e:
        log.debug(f"Firewall check failed for {hostname}: {e}")
    
    return findings

