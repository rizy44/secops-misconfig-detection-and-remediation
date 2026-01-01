"""
OpenStack Exposure Scanner

Scans for exposed resources (floating IPs, port security, etc.)
"""

import logging
from typing import List, Dict

log = logging.getLogger("secops")


def scan_floating_ips(conn) -> List[Dict]:
    """
    Scan for instances with floating IPs attached
    
    Args:
        conn: OpenStack connection
        
    Returns:
        List of findings
    """
    findings = []
    
    try:
        for server in conn.compute.servers(details=True):
            addresses = server.addresses or {}
            floating_ips = []
            fixed_ips = []
            
            for network_name, addr_list in addresses.items():
                for addr in addr_list:
                    ip_addr = addr.get("addr")
                    ip_type = addr.get("OS-EXT-IPS:type", "fixed")
                    
                    if ip_type == "floating":
                        floating_ips.append(ip_addr)
                    else:
                        fixed_ips.append(ip_addr)
            
            if floating_ips:
                details = {
                    "server_id": server.id,
                    "server_name": server.name,
                    "floating_ips": floating_ips,
                    "fixed_ips": fixed_ips,
                    "project_id": server.project_id
                }
                
                findings.append({
                    "type": "FIP_EXPOSED_INSTANCE",
                    "severity": "MEDIUM",
                    "resource_id": server.id,
                    "summary": f"Server {server.name} has floating IP(s) attached: {', '.join(floating_ips)}",
                    "details_json": details
                })
    except Exception as e:
        log.exception(f"Error scanning floating IPs: {e}")
    
    return findings


def scan_port_security(conn) -> List[Dict]:
    """
    Scan for ports with port_security_enabled=False
    
    Args:
        conn: OpenStack connection
        
    Returns:
        List of findings
    """
    findings = []
    
    try:
        for port in conn.network.ports():
            if not port.port_security_enabled:
                fixed_ips = []
                for fixed_ip in port.fixed_ips or []:
                    fixed_ips.append(fixed_ip.get("ip_address"))
                
                details = {
                    "port_id": port.id,
                    "network_id": port.network_id,
                    "device_id": port.device_id,
                    "fixed_ips": fixed_ips,
                    "project_id": port.project_id
                }
                
                findings.append({
                    "type": "PORT_SECURITY_DISABLED",
                    "severity": "HIGH",
                    "resource_id": port.id,
                    "summary": f"Port {port.id} has port_security_enabled=False",
                    "details_json": details
                })
    except Exception as e:
        log.exception(f"Error scanning port security: {e}")
    
    return findings

