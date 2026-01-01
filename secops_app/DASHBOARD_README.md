# SecOps Web Dashboard - Setup & Usage Guide

## Features

### 1. **Web Dashboard**
- Modern, responsive UI for monitoring security findings
- Real-time statistics and filtering
- Categorized by OpenStack service
- Easy-to-use interface for managing findings

### 2. **API Endpoint Scanner**
- Automatically scans 12 OpenStack API endpoints
- Detects:
  - Unauthenticated access
  - Missing security headers
  - Version information disclosure
  - Dangerous HTTP methods
  - Insecure protocols (HTTP vs HTTPS)

### 3. **Automated Remediation**
- Rule-based remediation engine
- YAML-based runbook catalog
- Execute fixes via OpenStack SDK
- Verification after remediation

## Setup Instructions

### 1. Update Infrastructure (Optional)

If you want to access the web dashboard from outside, apply the Terraform changes:

```bash
cd terraform
terraform plan
terraform apply
```

This will add a security group rule to allow port 8000 from your admin CIDR.

### 2. Deploy Application

```bash
cd ansible
ansible-playbook -i inventory.ini 04-secops-app.yml
```

This will:
- Copy updated code to secops_app VM
- Install dependencies
- Start the container

## Accessing the Dashboard

### Option 1: Via SSH Tunnel (Recommended)

```bash
# From your local machine
ssh -L 8000:10.10.50.163:8000 ubuntu@<obs_stack_floating_ip>

# Then open in browser
http://localhost:8000
```

### Option 2: Direct Access (if FIP enabled for secops_app)

If you enabled Floating IP for secops_app:

```bash
http://<secops_app_floating_ip>:8000
```

### Option 3: Via Gateway

From obs_stack gateway (if you have FIP):

```bash
ssh ubuntu@<obs_stack_floating_ip>
curl http://10.10.50.163:8000
```

## Using the Dashboard

### Main Features

1. **Statistics Cards**
   - Total Findings
   - High Severity Findings
   - Resolved Findings
   - Services Scanned

2. **Filters**
   - Filter by Service (Compute, Network, Identity, etc.)
   - Filter by Severity (HIGH, MEDIUM, LOW)
   - Filter by Status (new, remediating, resolved)

3. **Findings Table**
   - View all security findings
   - Click to view details
   - Sort and filter findings

4. **Remediation**
   - Click "Remediate" on any finding
   - Execute runbook-based fixes
   - View remediation results

### Workflow Example

1. **Scan Triggers**: Scanner runs automatically every 5 minutes
2. **View Findings**: Check dashboard for new findings
3. **Review Details**: Click on a finding to view details
4. **Remediate**: Execute remediation for the finding
5. **Verify**: Check if finding is resolved

## API Endpoints

All API endpoints are available:

- `GET /` - API information
- `GET /api/findings` - List findings (with filters)
- `GET /api/findings/{finding_id}` - Get finding details
- `GET /api/services` - List OpenStack services
- `POST /api/scan` - Trigger manual scan
- `POST /api/remediate/{finding_id}` - Execute remediation
- `GET /api/remediation` - List remediation runs
- `GET /api/remediation/{run_id}` - Get remediation run details
- `GET /metrics` - Prometheus metrics
- `GET /findings` - Legacy findings endpoint

## API Endpoints Being Scanned

The scanner checks these OpenStack API endpoints:

1. **Cloudformation** - `http://192.168.1.229:8000/v1`
2. **Compute** - `http://192.168.1.229:8774/v2.1`
3. **Compute_Legacy** - `http://192.168.1.229:8774/v2/...`
4. **Container_Infra** - `http://192.168.1.229:9511/v1`
5. **Identity** - `http://192.168.1.229:5000`
6. **Image** - `http://192.168.1.229:9292`
7. **Network** - `http://192.168.1.229:9696`
8. **Orchestration** - `http://192.168.1.229:8004/v1/...`
9. **Placement** - `http://192.168.1.229:8780`
10. **Share** - `http://192.168.1.229:8786/v1/...`
11. **Sharev2** - `http://192.168.1.229:8786/v2`
12. **Volumev3** - `http://192.168.1.229:8776/v3/...`

**Note**: Update IPs in `config.py` if your OpenStack endpoints are different.

## Configuration

Edit `secops_app/config.py` to customize:

```python
# Scanner settings
API_SCAN_TIMEOUT = 10  # seconds
API_SCAN_ENABLED = True

# Security checks
SECURITY_CHECKS = {
    "check_auth": True,
    "check_headers": True,
    "check_ssl": False,  # Enable for HTTPS endpoints
    "check_methods": True,
    "check_version": True,
}

# Remediation settings
ADMIN_CIDR = "192.168.0.0/16"
```

## Troubleshooting

### Dashboard not loading

```bash
# Check container logs
ssh ubuntu@<secops_app_ip>
cd /opt/secops/secops_app
docker compose logs -f
```

### No API findings

Check if endpoints are reachable from secops_app VM:

```bash
ssh ubuntu@<secops_app_ip>
curl -v http://192.168.1.229:5000
```

### Database errors

Reset database if schema changes:

```bash
ssh ubuntu@<secops_app_ip>
sudo rm /data/secops/findings.db
docker compose restart
```

## Security Considerations

1. **Network Access**: Port 8000 is accessible from admin_cidr
2. **Authentication**: Currently no auth on dashboard (add if needed)
3. **HTTPS**: Consider adding reverse proxy with SSL/TLS

## Next Steps

- [ ] Add authentication to web dashboard
- [ ] Expand scanner to check more OpenStack resources
- [ ] Add historical trends and charts
- [ ] Add email/Slack notifications for critical findings

## Support

For issues or questions, check:
- Container logs: `docker compose logs`
- Application logs: `/data/secops/secops.log`
- Database: `/data/secops/findings.db`
