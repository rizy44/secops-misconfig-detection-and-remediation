"""
OpenAI Service Module

Generates remediation suggestions for security findings using OpenAI API.
"""

import os
import logging
from typing import Dict, Optional
from openai import OpenAI
from services.normalize import normalize_finding

log = logging.getLogger("secops")


class OpenAIService:
    """Service for generating remediation suggestions using OpenAI"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize OpenAI service
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.client = None
        
        if self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                log.error(f"Failed to initialize OpenAI client: {e}")
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available"""
        return self.client is not None and bool(self.api_key)
    
    def generate_suggestion(self, finding: Dict) -> Optional[str]:
        """
        Generate remediation suggestion for a finding
        
        Args:
            finding: Finding dict with type, severity, summary, etc.
            
        Returns:
            Remediation suggestion text or None if failed
        """
        if not self.is_available():
            log.warning("OpenAI service not available (API key not configured)")
            return None
        
        try:
            # Build prompt based on finding
            prompt = self._build_prompt(finding)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a security expert specializing in OpenStack cloud infrastructure. "
                                   "Provide clear, actionable remediation steps for security findings. "
                                   "Format your response as numbered steps. Be specific and include "
                                   "actual commands or configuration changes where applicable."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            suggestion = response.choices[0].message.content.strip()
            # Use normalized finding to get canonical type
            finding_norm = normalize_finding(finding)
            log.info(f"Generated suggestion for finding type {finding_norm.get('type')}")
            
            return suggestion
            
        except Exception as e:
            log.error(f"Error generating suggestion: {e}")
            return None
    
    def _build_prompt(self, finding: Dict) -> str:
        """
        Build prompt for OpenAI based on finding details
        
        Args:
            finding: Finding dict (will be normalized to get canonical type)
            
        Returns:
            Formatted prompt string
        """
        # Normalize finding to get canonical type
        finding_norm = normalize_finding(finding)
        finding_type = finding_norm.get("type", "UNKNOWN")
        severity = finding_norm.get("severity", "UNKNOWN")
        summary = finding_norm.get("summary", "No summary available")
        service_name = finding_norm.get("service_name", "")
        endpoint_url = finding_norm.get("endpoint_url", "")
        
        prompt = f"""Security Finding Details:
- Type: {finding_type}
- Severity: {severity}
- Summary: {summary}"""
        
        if service_name:
            prompt += f"\n- Service: {service_name}"
        
        if endpoint_url:
            prompt += f"\n- Endpoint: {endpoint_url}"
        
        prompt += "\n\nPlease provide step-by-step remediation instructions to fix this security issue. "
        prompt += "Include specific commands, configuration file changes, or OpenStack CLI commands where applicable."
        
        return prompt
    
    def generate_bulk_suggestions(self, findings: list) -> Dict[int, str]:
        """
        Generate suggestions for multiple findings
        
        Args:
            findings: List of finding dicts with 'id' field
            
        Returns:
            Dict mapping finding_id to suggestion text
        """
        suggestions = {}
        
        for finding in findings:
            finding_id = finding.get("id")
            if finding_id:
                suggestion = self.generate_suggestion(finding)
                if suggestion:
                    suggestions[finding_id] = suggestion
        
        return suggestions








