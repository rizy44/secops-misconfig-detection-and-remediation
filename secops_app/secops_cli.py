#!/usr/bin/env python3
"""
SecOps CLI Tool
Query findings, generate suggestions, and manage SecOps API
"""

import sys
import json
import argparse
from typing import Optional
import requests
from datetime import datetime

# Default API URL
DEFAULT_API_URL = "http://localhost:8000"


def print_table(data, headers=None):
    """Print data as formatted table"""
    if not data:
        print("No data found")
        return
    
    if isinstance(data, dict):
        data = [data]
    
    if not headers:
        headers = list(data[0].keys())
    
    # Calculate column widths
    col_widths = {h: len(str(h)) for h in headers}
    for row in data:
        for h in headers:
            if h in row:
                col_widths[h] = max(col_widths[h], len(str(row[h])))
    
    # Print header
    header_row = " | ".join(str(h).ljust(col_widths[h]) for h in headers)
    print(header_row)
    print("-" * len(header_row))
    
    # Print rows
    for row in data:
        print(" | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers))


def list_findings(api_url: str, limit: int, severity: Optional[str], 
                  service: Optional[str], status: Optional[str], format: str):
    """List findings"""
    url = f"{api_url}/api/findings"
    params = {"limit": limit}
    
    if severity:
        params["severity"] = severity
    if service:
        params["service"] = service
    if status:
        params["status"] = status
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        findings = response.json()
        
        if format == "json":
            print(json.dumps(findings, indent=2))
        else:
            if not findings:
                print("No findings found")
                return
            
            # Format findings for table
            formatted = []
            for f in findings:
                ts = datetime.fromtimestamp(f.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
                formatted.append({
                    "ID": f.get("id"),
                    "Type": f.get("ftype"),
                    "Severity": f.get("severity"),
                    "Service": f.get("service_name") or "N/A",
                    "Summary": (f.get("summary") or "")[:50],
                    "Status": f.get("status", "new"),
                    "Time": ts
                })
            
            print_table(formatted)
            print(f"\nTotal: {len(findings)} findings")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def list_services(api_url: str, format: str):
    """List services"""
    url = f"{api_url}/api/services"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        services = response.json()
        
        if format == "json":
            print(json.dumps(services, indent=2))
        else:
            formatted = [{"Service": s.get("name"), "Findings": s.get("finding_count", 0)} 
                        for s in services]
            print_table(formatted)
            print(f"\nTotal: {len(services)} services")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def trigger_scan(api_url: str):
    """Trigger manual scan"""
    url = f"{api_url}/api/scan"
    
    try:
        print("Triggering scan...")
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()
        print(f"✓ {result.get('message', 'Scan completed')}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def generate_suggestion(api_url: str, finding_id: int, format: str):
    """Generate AI suggestion for a finding"""
    url = f"{api_url}/api/suggestions/{finding_id}"
    
    try:
        print(f"Generating suggestion for finding {finding_id}...")
        response = requests.post(url)
        
        if response.status_code == 503:
            print("Error: OpenAI service not configured")
            sys.exit(1)
        
        response.raise_for_status()
        suggestion = response.json()
        
        if format == "json":
            print(json.dumps(suggestion, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"Suggestion ID: {suggestion.get('id')}")
            print(f"Finding ID: {suggestion.get('finding_id')}")
            print(f"Status: {suggestion.get('status')}")
            print(f"\n{'='*60}")
            print(suggestion.get("suggestion_text", ""))
            print(f"{'='*60}\n")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def list_suggestions(api_url: str, finding_id: Optional[int], status: Optional[str], format: str):
    """List suggestions"""
    url = f"{api_url}/api/suggestions"
    params = {}
    
    if finding_id:
        params["finding_id"] = finding_id
    if status:
        params["status"] = status
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        suggestions = response.json()
        
        if format == "json":
            print(json.dumps(suggestions, indent=2))
        else:
            if not suggestions:
                print("No suggestions found")
                return
            
            formatted = []
            for s in suggestions:
                formatted.append({
                    "ID": s.get("id"),
                    "Finding ID": s.get("finding_id"),
                    "Status": s.get("status"),
                    "Preview": (s.get("suggestion_text", "")[:50] + "...") if len(s.get("suggestion_text", "")) > 50 else s.get("suggestion_text", "")
                })
            
            print_table(formatted)
            print(f"\nTotal: {len(suggestions)} suggestions")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def approve_suggestion(api_url: str, suggestion_id: int):
    """Approve a suggestion"""
    url = f"{api_url}/api/suggestions/{suggestion_id}/approve"
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()
        print(f"✓ {result.get('message', 'Suggestion approved')}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def reject_suggestion(api_url: str, suggestion_id: int):
    """Reject a suggestion"""
    url = f"{api_url}/api/suggestions/{suggestion_id}/reject"
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()
        print(f"✓ {result.get('message', 'Suggestion rejected')}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def show_finding(api_url: str, finding_id: int, format: str):
    """Show detailed finding by ID"""
    url = f"{api_url}/api/findings/{finding_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        finding = response.json()
        
        if format == "json":
            print(json.dumps(finding, indent=2))
        else:
            # Format timestamp
            try:
                ts = datetime.fromtimestamp(finding.get("ts", 0)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                ts = str(finding.get("ts", "N/A"))
            
            print("=" * 60)
            print(f"Finding ID: {finding.get('id')}")
            print("=" * 60)
            print(f"Type:      {finding.get('ftype', 'N/A')}")
            print(f"Severity:  {finding.get('severity', 'N/A')}")
            print(f"Status:    {finding.get('status', 'new')}")
            print(f"Service:   {finding.get('service_name', 'N/A')}")
            print(f"Endpoint:  {finding.get('endpoint_url', 'N/A')}")
            print(f"Resource:  {finding.get('resource_id', 'N/A')}")
            print(f"Time:      {ts}")
            print(f"\nSummary:")
            print(f"  {finding.get('summary', 'N/A')}")
            print("=" * 60)
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Finding ID {finding_id} not found", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def show_suggestion(api_url: str, suggestion_id: int, format: str):
    """Show detailed suggestion by ID"""
    url = f"{api_url}/api/suggestions/{suggestion_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        suggestion = response.json()
        
        if format == "json":
            print(json.dumps(suggestion, indent=2))
        else:
            # Format timestamps
            try:
                created_at = datetime.fromtimestamp(suggestion.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                created_at = str(suggestion.get("created_at", "N/A"))
            
            try:
                updated_at = datetime.fromtimestamp(suggestion.get("updated_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                updated_at = str(suggestion.get("updated_at", "N/A"))
            
            print("=" * 60)
            print(f"Suggestion ID: {suggestion.get('id')}")
            print("=" * 60)
            print(f"Finding ID:  {suggestion.get('finding_id')}")
            print(f"Status:      {suggestion.get('status', 'pending')}")
            print(f"Created:     {created_at}")
            print(f"Updated:     {updated_at}")
            print(f"\n{'='*60}")
            print("Suggestion Text:")
            print(f"{'='*60}")
            print(suggestion.get("suggestion_text", "N/A"))
            print(f"{'='*60}")
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Suggestion ID {suggestion_id} not found", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def remediate_finding(api_url: str, finding_id: int, force: bool, format: str):
    """Remediate a finding"""
    url = f"{api_url}/api/remediate/{finding_id}"
    params = {}
    if force:
        params["force"] = "true"
    
    try:
        print(f"Remediating finding {finding_id}...")
        response = requests.post(url, params=params)
        response.raise_for_status()
        result = response.json()
        
        if format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"✓ Remediation started")
            print(f"  Run ID: {result.get('run_id')}")
            print(f"  Status: {result.get('status')}")
            print(f"  Message: {result.get('message')}")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def list_remediation_runs(api_url: str, finding_id: Optional[int], format: str):
    """List remediation runs"""
    url = f"{api_url}/api/remediation"
    params = {}
    if finding_id:
        params["finding_id"] = finding_id
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        runs = response.json()
        
        if format == "json":
            print(json.dumps(runs, indent=2))
        else:
            if not runs:
                print("No remediation runs found")
                return
            
            formatted = []
            for r in runs:
                try:
                    started_at = datetime.fromtimestamp(r.get("started_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    started_at = str(r.get("started_at", "N/A"))
                
                formatted.append({
                    "ID": r.get("id"),
                    "Finding ID": r.get("finding_id"),
                    "Runbook": r.get("runbook_id"),
                    "Status": r.get("status"),
                    "Started": started_at
                })
            
            print_table(formatted)
            print(f"\nTotal: {len(runs)} runs")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def show_remediation_run(api_url: str, run_id: int, format: str):
    """Show remediation run details"""
    url = f"{api_url}/api/remediation/{run_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        run = response.json()
        
        if format == "json":
            print(json.dumps(run, indent=2))
        else:
            try:
                started_at = datetime.fromtimestamp(run.get("started_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            except:
                started_at = str(run.get("started_at", "N/A"))
            
            try:
                finished_at = datetime.fromtimestamp(run.get("finished_at", 0)).strftime("%Y-%m-%d %H:%M:%S") if run.get("finished_at") else "N/A"
            except:
                finished_at = str(run.get("finished_at", "N/A"))
            
            print("=" * 60)
            print(f"Remediation Run ID: {run.get('id')}")
            print("=" * 60)
            print(f"Finding ID:  {run.get('finding_id')}")
            print(f"Runbook:     {run.get('runbook_id')}")
            print(f"Status:       {run.get('status')}")
            print(f"Started:      {started_at}")
            print(f"Finished:     {finished_at}")
            
            if run.get("stdout"):
                print(f"\n{'='*60}")
                print("STDOUT:")
                print(f"{'='*60}")
                print(run.get("stdout"))
            
            if run.get("stderr"):
                print(f"\n{'='*60}")
                print("STDERR:")
                print(f"{'='*60}")
                print(run.get("stderr"))
            
            print("=" * 60)
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: Remediation run ID {run_id} not found", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def get_stats(api_url: str):
    """Get statistics"""
    try:
        # Get findings
        findings_response = requests.get(f"{api_url}/api/findings?limit=1000")
        findings_response.raise_for_status()
        findings = findings_response.json()
        
        # Get services
        services_response = requests.get(f"{api_url}/api/services")
        services_response.raise_for_status()
        services = services_response.json()
        
        # Get suggestions
        suggestions_response = requests.get(f"{api_url}/api/suggestions")
        suggestions_response.raise_for_status()
        suggestions = suggestions_response.json()
        
        # Calculate stats
        total_findings = len(findings)
        high_severity = len([f for f in findings if f.get("severity") == "HIGH"])
        pending_suggestions = len([s for s in suggestions if s.get("status") == "pending"])
        total_services = len(services)
        
        print("=" * 40)
        print("SecOps Statistics")
        print("=" * 40)
        print(f"Total Findings:      {total_findings}")
        print(f"High Severity:       {high_severity}")
        print(f"Pending Suggestions: {pending_suggestions}")
        print(f"Services Scanned:    {total_services}")
        print("=" * 40)
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="SecOps CLI - Query findings and manage security scans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all findings
  %(prog)s findings list
  
  # List HIGH severity findings
  %(prog)s findings list --severity HIGH
  
  # Show finding details by ID
  %(prog)s findings show 123
  
  # List findings in JSON format
  %(prog)s findings list --format json
  
  # Trigger scan
  %(prog)s scan
  
  # Generate suggestion for finding ID 123
  %(prog)s suggestions generate 123
  
  # Show suggestion details by ID
  %(prog)s suggestions show 456
  
  # Get statistics
  %(prog)s stats
        """
    )
    
    parser.add_argument("--api-url", default=DEFAULT_API_URL,
                       help=f"API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--format", choices=["table", "json"], default="table",
                       help="Output format (default: table)")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Findings commands
    findings_parser = subparsers.add_parser("findings", help="Findings operations")
    findings_subparsers = findings_parser.add_subparsers(dest="findings_action")
    
    list_parser = findings_subparsers.add_parser("list", help="List findings")
    list_parser.add_argument("--limit", type=int, default=50, help="Limit (default: 50)")
    list_parser.add_argument("--severity", choices=["HIGH", "MEDIUM", "LOW"], help="Filter by severity")
    list_parser.add_argument("--service", help="Filter by service name")
    list_parser.add_argument("--status", choices=["new", "approved", "rejected", "remediating", "remediated_unverified", "resolved", "remediation_failed", "verify_failed"], help="Filter by status")
    
    show_finding_parser = findings_subparsers.add_parser("show", help="Show finding details")
    show_finding_parser.add_argument("finding_id", type=int, help="Finding ID")
    
    # Services commands
    services_parser = subparsers.add_parser("services", help="Services operations")
    services_subparsers = services_parser.add_subparsers(dest="services_action")
    services_subparsers.add_parser("list", help="List services")
    
    # Scan commands
    subparsers.add_parser("scan", help="Trigger manual scan")
    
    # Suggestions commands
    suggestions_parser = subparsers.add_parser("suggestions", help="Suggestions operations")
    suggestions_subparsers = suggestions_parser.add_subparsers(dest="suggestions_action")
    
    list_sugg_parser = suggestions_subparsers.add_parser("list", help="List suggestions")
    list_sugg_parser.add_argument("--finding-id", type=int, dest="finding_id", help="Filter by finding ID")
    list_sugg_parser.add_argument("--status", choices=["pending", "approved", "rejected"], help="Filter by status")
    
    generate_parser = suggestions_subparsers.add_parser("generate", help="Generate suggestion")
    generate_parser.add_argument("finding_id", type=int, help="Finding ID")
    
    show_suggestion_parser = suggestions_subparsers.add_parser("show", help="Show suggestion details")
    show_suggestion_parser.add_argument("suggestion_id", type=int, help="Suggestion ID")
    
    approve_parser = suggestions_subparsers.add_parser("approve", help="Approve suggestion")
    approve_parser.add_argument("suggestion_id", type=int, help="Suggestion ID")
    
    reject_parser = suggestions_subparsers.add_parser("reject", help="Reject suggestion")
    reject_parser.add_argument("suggestion_id", type=int, help="Suggestion ID")
    
    # Remediation commands
    remediation_parser = subparsers.add_parser("remediate", help="Remediation operations")
    remediation_subparsers = remediation_parser.add_subparsers(dest="remediation_action")
    
    remediate_parser = remediation_subparsers.add_parser("run", help="Remediate a finding")
    remediate_parser.add_argument("finding_id", type=int, help="Finding ID")
    remediate_parser.add_argument("--force", action="store_true", help="Force remediation without approval")
    
    remediation_runs_parser = remediation_subparsers.add_parser("runs", help="List remediation runs")
    remediation_runs_parser.add_argument("--finding-id", type=int, dest="finding_id", help="Filter by finding ID")
    
    remediation_show_parser = remediation_subparsers.add_parser("show", help="Show remediation run details")
    remediation_show_parser.add_argument("run_id", type=int, help="Remediation run ID")
    
    # Stats command
    subparsers.add_parser("stats", help="Show statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Route to appropriate function
    if args.command == "findings":
        if args.findings_action == "list":
            list_findings(args.api_url, args.limit, args.severity, args.service, args.status, args.format)
        elif args.findings_action == "show":
            show_finding(args.api_url, args.finding_id, args.format)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "services" and args.services_action == "list":
        list_services(args.api_url, args.format)
    elif args.command == "scan":
        trigger_scan(args.api_url)
    elif args.command == "suggestions":
        if args.suggestions_action == "generate":
            generate_suggestion(args.api_url, args.finding_id, args.format)
        elif args.suggestions_action == "list":
            finding_id = getattr(args, 'finding_id', None)
            status = getattr(args, 'status', None)
            list_suggestions(args.api_url, finding_id, status, args.format)
        elif args.suggestions_action == "show":
            show_suggestion(args.api_url, args.suggestion_id, args.format)
        elif args.suggestions_action == "approve":
            approve_suggestion(args.api_url, args.suggestion_id)
        elif args.suggestions_action == "reject":
            reject_suggestion(args.api_url, args.suggestion_id)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "remediate":
        if args.remediation_action == "run":
            remediate_finding(args.api_url, args.finding_id, args.force, args.format)
        elif args.remediation_action == "runs":
            finding_id = getattr(args, 'finding_id', None)
            list_remediation_runs(args.api_url, finding_id, args.format)
        elif args.remediation_action == "show":
            show_remediation_run(args.api_url, args.run_id, args.format)
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "stats":
        get_stats(args.api_url)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

