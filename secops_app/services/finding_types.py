"""
Finding Types - Canonical Types and Legacy Mappings

Defines canonical finding types and mappings from legacy types to canonical types.
"""

# Canonical finding types
CANONICAL_TYPES = {
    # Security Group types
    "SG_WORLD_OPEN_SSH": "Security group allows SSH (tcp/22) from 0.0.0.0/0",
    "SG_WORLD_OPEN_RDP": "Security group allows RDP (tcp/3389) from 0.0.0.0/0",
    "SG_WORLD_OPEN_DB_PORT": "Security group allows database port from 0.0.0.0/0",
    
    # Exposure types
    "FIP_EXPOSED_INSTANCE": "Instance has floating IP attached (exposed to internet)",
    "PORT_SECURITY_DISABLED": "Neutron port has port_security_enabled=False",
    
    # Error states
    "INSTANCE_ERROR_STATE": "Instance is in ERROR state",
    "VOLUME_ERROR_STATE": "Volume is in error state",
    
    # OS baseline types
    "OS_SSH_PASSWORD_AUTH_ENABLED": "SSH password authentication is enabled",
    "OS_SSH_ROOT_LOGIN_ENABLED": "SSH root login is enabled",
    "OS_FIREWALL_DISABLED": "Firewall (ufw/firewalld) is not running",
    "OS_SCAN_UNREACHABLE": "Instance is unreachable for OS baseline scan",
}

# Legacy type to canonical type mapping
TYPE_ALIASES = {
    # Security Group legacy mappings
    "SG_OPEN_SSH": "SG_WORLD_OPEN_SSH",
    "SG_OPEN_RDP": "SG_WORLD_OPEN_RDP",
    
    # Error state legacy mappings
    "NOVA_SERVER_ERROR": "INSTANCE_ERROR_STATE",
    "CINDER_VOLUME_ERROR": "VOLUME_ERROR_STATE",
    
    # API endpoint types (keep as-is, optional canonicalization)
    # "API_UNAUTHENTICATED_ACCESS": "API_UNAUTHENTICATED_ACCESS",
    # "API_MISSING_SECURITY_HEADERS": "API_MISSING_SECURITY_HEADERS",
    # etc.
}

def get_canonical_type(raw_type: str) -> str:
    """
    Get canonical type from raw/legacy type
    
    Args:
        raw_type: Raw finding type (legacy or canonical)
        
    Returns:
        Canonical type string
    """
    if not raw_type:
        return "UNKNOWN"
    
    # Check if it's already canonical
    if raw_type in CANONICAL_TYPES:
        return raw_type
    
    # Check legacy mapping
    return TYPE_ALIASES.get(raw_type, raw_type)

