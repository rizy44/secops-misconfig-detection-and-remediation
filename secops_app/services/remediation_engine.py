"""
Remediation Engine

Executes remediation runbooks from catalog based on finding types.
Supports control-plane (OpenStack SDK) and OS-level (Ansible) runbooks.
"""

import os
import json
import logging
import subprocess
import yaml
from typing import Dict, Optional, Any, List
from openstack import connection
from services.normalize import normalize_finding

log = logging.getLogger("secops")


class RemediationEngine:
    """Engine for executing remediation runbooks"""
    
    def __init__(self, catalog_path: str, db_path: str):
        """
        Initialize remediation engine
        
        Args:
            catalog_path: Path to catalog.yml file
            db_path: Path to SQLite database
        """
        self.catalog_path = catalog_path
        self.db_path = db_path
        self.catalog = self._load_catalog()
    
    def _load_catalog(self) -> Dict[str, Any]:
        """Load runbook catalog from YAML file"""
        try:
            with open(self.catalog_path, 'r') as f:
                catalog = yaml.safe_load(f)
            
            # Substitute environment variables in params
            catalog = self._substitute_env_vars(catalog)
            log.info(f"Loaded remediation catalog with {len(catalog)} runbooks")
            return catalog or {}
        except FileNotFoundError:
            log.error(f"Catalog file not found: {self.catalog_path}")
            return {}
        except Exception as e:
            log.error(f"Error loading catalog: {e}")
            return {}
    
    def _substitute_env_vars(self, catalog: Dict) -> Dict:
        """Substitute ${VAR} with environment variables"""
        if isinstance(catalog, dict):
            result = {}
            for k, v in catalog.items():
                if isinstance(v, dict):
                    if "params" in v and isinstance(v["params"], dict):
                        params = {}
                        for param_k, param_v in v["params"].items():
                            if isinstance(param_v, str) and param_v.startswith("${") and param_v.endswith("}"):
                                env_var = param_v[2:-1]
                                params[param_k] = os.environ.get(env_var, param_v)
                            else:
                                params[param_k] = param_v
                        v["params"] = params
                    result[k] = self._substitute_env_vars(v)
                else:
                    result[k] = v
            return result
        elif isinstance(catalog, list):
            return [self._substitute_env_vars(item) for item in catalog]
        else:
            return catalog
    
    def resolve_runbook(self, finding: Dict) -> Optional[str]:
        """
        Resolve runbook_id from finding type
        
        Args:
            finding: Finding dict (will be normalized)
            
        Returns:
            Runbook ID or None if not found
        """
        finding_norm = normalize_finding(finding)
        canonical_type = finding_norm.get("type")
        
        # Search catalog for matching runbook
        for runbook_id, runbook_def in self.catalog.items():
            finding_types = runbook_def.get("finding_types", [])
            aliases = runbook_def.get("aliases", [])
            
            if canonical_type in finding_types or canonical_type in aliases:
                return runbook_id
        
        log.warning(f"No runbook found for finding type: {canonical_type}")
        return None
    
    def execute_runbook(
        self,
        finding_id: int,
        runbook_id: str,
        finding: Dict,
        conn: connection.Connection
    ) -> Dict[str, Any]:
        """
        Execute a remediation runbook
        
        Args:
            finding_id: Finding ID
            runbook_id: Runbook ID from catalog
            finding: Finding dict
            conn: OpenStack connection
            
        Returns:
            Dict with status, stdout, stderr
        """
        if runbook_id not in self.catalog:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": f"Runbook {runbook_id} not found in catalog"
            }
        
        runbook_def = self.catalog[runbook_id]
        params = runbook_def.get("params", {})
        finding_norm = normalize_finding(finding)
        
        # Determine runbook type and execute
        if runbook_id.startswith("rb_sg_"):
            return self._execute_sg_runbook(finding_id, runbook_id, finding_norm, params, conn)
        elif runbook_id == "rb_detach_floating_ip":
            return self._execute_fip_runbook(finding_id, finding_norm, params, conn)
        elif runbook_id == "rb_enable_port_security":
            return self._execute_port_security_runbook(finding_id, finding_norm, params, conn)
        elif runbook_id.startswith("rb_os_"):
            return self._execute_os_runbook(finding_id, runbook_id, finding_norm, params)
        else:
            return {
                "status": "failed",
                "stdout": "",
                "stderr": f"Unknown runbook type: {runbook_id}"
            }
    
    def _execute_sg_runbook(
        self,
        finding_id: int,
        runbook_id: str,
        finding: Dict,
        params: Dict,
        conn: connection.Connection
    ) -> Dict[str, Any]:
        """Execute security group remediation runbook"""
        try:
            # Extract details from finding
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            sg_id = details.get("sg_id") or finding.get("resource_id")
            if not sg_id:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "Missing security group ID"
                }
            
            # Determine port from runbook type
            port = 22  # default SSH
            if "rdp" in runbook_id:
                port = 3389
            elif "db" in runbook_id:
                # For DB ports, we need to get from details
                port = details.get("port_min") or details.get("port_max")
                if not port:
                    return {
                        "status": "failed",
                        "stdout": "",
                        "stderr": "Missing database port in details"
                    }
            
            admin_cidr = params.get("admin_cidr", "192.168.0.0/16")
            
            # Get security group
            sg = conn.network.find_security_group(sg_id)
            if not sg:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"Security group {sg_id} not found"
                }
            
            stdout_lines = []
            stderr_lines = []
            
            # Find and delete world-open rule
            world_rule = None
            for rule in sg.security_group_rules:
                if (rule.get("direction") == "ingress" and
                    rule.get("remote_ip_prefix") == "0.0.0.0/0" and
                    rule.get("protocol") == "tcp" and
                    rule.get("port_range_min") == port and
                    rule.get("port_range_max") == port):
                    world_rule = rule
                    break
            
            if world_rule:
                try:
                    conn.network.delete_security_group_rule(world_rule["id"])
                    stdout_lines.append(f"Deleted world-open rule {world_rule['id']} for tcp/{port}")
                except Exception as e:
                    stderr_lines.append(f"Error deleting world-open rule: {e}")
                    return {
                        "status": "failed",
                        "stdout": "\n".join(stdout_lines),
                        "stderr": "\n".join(stderr_lines)
                    }
            else:
                stdout_lines.append(f"No world-open rule found for tcp/{port} (already fixed?)")
            
            # Check if admin_cidr rule already exists
            admin_rule_exists = False
            for rule in sg.security_group_rules:
                if (rule.get("direction") == "ingress" and
                    rule.get("remote_ip_prefix") == admin_cidr and
                    rule.get("protocol") == "tcp" and
                    rule.get("port_range_min") == port and
                    rule.get("port_range_max") == port):
                    admin_rule_exists = True
                    break
            
            # Add admin_cidr rule if not exists
            if not admin_rule_exists:
                try:
                    conn.network.create_security_group_rule(
                        security_group_id=sg_id,
                        direction="ingress",
                        protocol="tcp",
                        port_range_min=port,
                        port_range_max=port,
                        remote_ip_prefix=admin_cidr
                    )
                    stdout_lines.append(f"Added rule for {admin_cidr} tcp/{port}")
                except Exception as e:
                    stderr_lines.append(f"Error adding admin rule: {e}")
                    return {
                        "status": "failed",
                        "stdout": "\n".join(stdout_lines),
                        "stderr": "\n".join(stderr_lines)
                    }
            else:
                stdout_lines.append(f"Admin rule for {admin_cidr} tcp/{port} already exists")
            
            return {
                "status": "success",
                "stdout": "\n".join(stdout_lines),
                "stderr": "\n".join(stderr_lines)
            }
            
        except Exception as e:
            log.exception(f"Error executing SG runbook: {e}")
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e)
            }
    
    def _execute_fip_runbook(
        self,
        finding_id: int,
        finding: Dict,
        params: Dict,
        conn: connection.Connection
    ) -> Dict[str, Any]:
        """Execute floating IP detach runbook"""
        try:
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            server_id = details.get("server_id") or finding.get("resource_id")
            floating_ips = details.get("floating_ips", [])
            
            if not server_id:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "Missing server ID"
                }
            
            stdout_lines = []
            stderr_lines = []
            
            # Get server
            server = conn.compute.find_server(server_id)
            if not server:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"Server {server_id} not found"
                }
            
            # Detach all floating IPs
            for fip_addr in floating_ips:
                try:
                    # Find floating IP
                    fip = conn.network.find_ip(fip_addr)
                    if fip and fip.port_id:
                        conn.network.update_ip(fip.id, port_id=None)
                        stdout_lines.append(f"Detached floating IP {fip_addr} from server {server_id}")
                    else:
                        stdout_lines.append(f"Floating IP {fip_addr} not found or already detached")
                except Exception as e:
                    stderr_lines.append(f"Error detaching {fip_addr}: {e}")
            
            if stderr_lines:
                return {
                    "status": "failed",
                    "stdout": "\n".join(stdout_lines),
                    "stderr": "\n".join(stderr_lines)
                }
            
            return {
                "status": "success",
                "stdout": "\n".join(stdout_lines) if stdout_lines else "No floating IPs to detach",
                "stderr": "\n".join(stderr_lines)
            }
            
        except Exception as e:
            log.exception(f"Error executing FIP runbook: {e}")
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e)
            }
    
    def _execute_port_security_runbook(
        self,
        finding_id: int,
        finding: Dict,
        params: Dict,
        conn: connection.Connection
    ) -> Dict[str, Any]:
        """Execute port security enable runbook"""
        try:
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            port_id = details.get("port_id") or finding.get("resource_id")
            if not port_id:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "Missing port ID"
                }
            
            # Update port
            try:
                conn.network.update_port(port_id, port_security_enabled=True)
                return {
                    "status": "success",
                    "stdout": f"Enabled port security on port {port_id}",
                    "stderr": ""
                }
            except Exception as e:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"Error updating port: {e}"
                }
            
        except Exception as e:
            log.exception(f"Error executing port security runbook: {e}")
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e)
            }
    
    def _execute_os_runbook(
        self,
        finding_id: int,
        runbook_id: str,
        finding: Dict,
        params: Dict
    ) -> Dict[str, Any]:
        """Execute OS-level runbook via Ansible"""
        try:
            ansible_inventory = params.get("ansible_inventory")
            if not ansible_inventory or not os.path.exists(ansible_inventory):
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"Ansible inventory not found: {ansible_inventory}"
                }
            
            # Get server details
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            server_ip = details.get("floating_ip") or details.get("fixed_ip")
            if not server_ip:
                return {
                    "status": "failed",
                    "stdout": "",
                    "stderr": "Missing server IP for OS remediation"
                }
            
            # For now, return not implemented (can be extended with actual Ansible playbook)
            return {
                "status": "failed",
                "stdout": "",
                "stderr": "OS runbooks require Ansible playbook implementation"
            }
            
        except Exception as e:
            log.exception(f"Error executing OS runbook: {e}")
            return {
                "status": "failed",
                "stdout": "",
                "stderr": str(e)
            }
    
    def verify_remediation(
        self,
        finding_id: int,
        runbook_id: str,
        finding: Dict,
        conn: connection.Connection
    ) -> bool:
        """
        Verify that remediation was successful
        
        Args:
            finding_id: Finding ID
            runbook_id: Runbook ID that was executed
            finding: Finding dict
            conn: OpenStack connection
            
        Returns:
            True if verification passes, False otherwise
        """
        finding_norm = normalize_finding(finding)
        canonical_type = finding_norm.get("type")
        
        try:
            if canonical_type in ["SG_WORLD_OPEN_SSH", "SG_WORLD_OPEN_RDP", "SG_WORLD_OPEN_DB_PORT"]:
                return self._verify_sg_remediation(finding_norm, conn)
            elif canonical_type == "FIP_EXPOSED_INSTANCE":
                return self._verify_fip_remediation(finding_norm, conn)
            elif canonical_type == "PORT_SECURITY_DISABLED":
                return self._verify_port_security_remediation(finding_norm, conn)
            else:
                log.warning(f"No verify function for type: {canonical_type}")
                return True  # Assume OK if no verify function
        except Exception as e:
            log.exception(f"Error verifying remediation: {e}")
            return False
    
    def _verify_sg_remediation(self, finding: Dict, conn: connection.Connection) -> bool:
        """Verify security group remediation"""
        try:
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            sg_id = details.get("sg_id") or finding.get("resource_id")
            if not sg_id:
                return False
            
            sg = conn.network.find_security_group(sg_id)
            if not sg:
                return False
            
            # Check for world-open rules on sensitive ports
            for rule in sg.security_group_rules:
                if (rule.get("direction") == "ingress" and
                    rule.get("remote_ip_prefix") == "0.0.0.0/0" and
                    rule.get("protocol") == "tcp"):
                    port = rule.get("port_range_min")
                    if port in [22, 3389] or port in [3306, 5432, 6379, 27017]:
                        log.warning(f"World-open rule still exists for tcp/{port}")
                        return False
            
            return True
        except Exception as e:
            log.exception(f"Error verifying SG remediation: {e}")
            return False
    
    def _verify_fip_remediation(self, finding: Dict, conn: connection.Connection) -> bool:
        """Verify floating IP remediation"""
        try:
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            server_id = details.get("server_id") or finding.get("resource_id")
            if not server_id:
                return False
            
            server = conn.compute.find_server(server_id)
            if not server:
                return False
            
            # Check if server has floating IPs
            addresses = server.addresses or {}
            for network_name, addr_list in addresses.items():
                for addr in addr_list:
                    if addr.get("OS-EXT-IPS:type") == "floating":
                        log.warning(f"Server still has floating IP: {addr.get('addr')}")
                        return False
            
            return True
        except Exception as e:
            log.exception(f"Error verifying FIP remediation: {e}")
            return False
    
    def _verify_port_security_remediation(self, finding: Dict, conn: connection.Connection) -> bool:
        """Verify port security remediation"""
        try:
            details_json = finding.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json) if details_json else {}
            else:
                details = details_json
            
            port_id = details.get("port_id") or finding.get("resource_id")
            if not port_id:
                return False
            
            port = conn.network.find_port(port_id)
            if not port:
                return False
            
            return port.port_security_enabled == True
        except Exception as e:
            log.exception(f"Error verifying port security remediation: {e}")
            return False

