"""
Finding Normalization Module

Normalizes finding dictionaries to use canonical types while preserving backward compatibility.
"""

import logging
from typing import Dict, Any
from services.finding_types import get_canonical_type

log = logging.getLogger("secops")


def normalize_finding(finding: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a finding dict to use canonical types
    
    Args:
        finding: Finding dict with 'ftype' or 'type' field
        
    Returns:
        Normalized finding dict with:
        - 'raw_type': original type from finding
        - 'type': canonical type
        - 'ftype': preserved for backward compatibility (DB column)
        - All other fields preserved
    """
    # Extract raw type from finding
    raw_type = None
    if "ftype" in finding and finding["ftype"]:
        raw_type = finding["ftype"]
    elif "type" in finding and finding["type"]:
        raw_type = finding["type"]
    
    if not raw_type:
        raw_type = "UNKNOWN"
        log.warning(f"Finding missing type field: {finding.get('id', 'unknown')}")
    
    # Get canonical type
    canonical_type = get_canonical_type(raw_type)
    
    # Build normalized finding
    normalized = finding.copy()
    normalized["raw_type"] = raw_type
    normalized["type"] = canonical_type
    
    # Preserve 'ftype' for backward compatibility (DB column)
    if "ftype" not in normalized:
        normalized["ftype"] = raw_type
    
    return normalized

