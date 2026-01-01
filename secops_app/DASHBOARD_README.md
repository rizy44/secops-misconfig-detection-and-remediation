# SecOps Web Dashboard - Setup & Usage Guide

## New Features

### 1. **Web Dashboard**
- Modern, responsive UI for monitoring security findings
- Real-time statistics and filtering
- Phân mục theo OpenStack service
- Easy-to-use interface for managing findings

### 2. **API Endpoint Scanner**
- Automatically scans 12 OpenStack API endpoints
- Detects:
  - Unauthenticated access
  - Missing security headers
  - Version information disclosure
  - Dangerous HTTP methods
  - Insecure protocols (HTTP vs HTTPS)

### 3. **OpenAI Integration**
- AI-powered remediation suggestions
- Step-by-step fix instructions
- Contextual recommendations based on finding type

### 4. **Approval Workflow**
- Review AI suggestions before implementation
- Approve or reject recommendations
- Track suggestion status (pending/approved/rejected)

## Setup Instructions

### 1. Configure OpenAI API Key

Set your OpenAI API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

Or add it to `secops_app/openstack.env`:

```bash
echo "OPENAI_API_KEY=sk-your-api-key-here" >> /opt/secops/secops_app/openstack.env
```

### 2. Update Infrastructure (Optional)

If you want to access the web dashboard from outside, apply the Terraform changes:

```bash
cd terraform
terraform plan
terraform apply
```

This will add a security group rule to allow port 8000 from your admin CIDR.

### 3. Deploy Updated Application

```bash
cd ansible
ansible-playbook -i inventory.ini 04-secops-app.yml
```

This will:
- Copy updated code to secops_app VM
- Install new dependencies (openai, httpx, jinja2)
- Restart the container with new environment variables

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
   - Pending Suggestions
   - Services Scanned

2. **Filters**
   - Filter by Service (Compute, Network, Identity, etc.)
   - Filter by Severity (HIGH, MEDIUM, LOW)
   - Filter by Status (new, approved, rejected)

3. **Findings Table**
   - View all security findings
   - Click "Get Suggestion" to generate AI recommendations
   - Sort and filter findings

4. **AI Suggestions**
   - Click "Get Suggestion" on any finding
   - Review AI-generated remediation steps
   - Approve or Reject the suggestion

### Workflow Example

1. **Scan Triggers**: Scanner runs automatically every 60 seconds
2. **View Findings**: Check dashboard for new findings
3. **Get Suggestion**: Click "Get Suggestion" for a finding
4. **Review**: Read AI-generated remediation steps
5. **Approve/Reject**: Approve to mark as actionable, or reject if not applicable
6. **Track**: Monitor status changes in the findings table

## API Endpoints

All API endpoints are available:

- `GET /` - Web Dashboard
- `GET /api/findings` - List findings (with filters)
- `GET /api/services` - List OpenStack services
- `POST /api/scan` - Trigger manual scan
- `POST /api/suggestions/{finding_id}` - Generate suggestion
- `GET /api/suggestions` - List suggestions
- `POST /api/suggestions/{suggestion_id}/approve` - Approve suggestion
- `POST /api/suggestions/{suggestion_id}/reject` - Reject suggestion
- `GET /metrics` - Prometheus metrics (legacy)
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
# OpenAI settings
OPENAI_MODEL = "gpt-4"  # or "gpt-3.5-turbo" for faster/cheaper

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
```

## Troubleshooting

### OpenAI not working

```bash
# Check if API key is set
ssh ubuntu@<secops_app_ip>
docker exec -it secops_api printenv | grep OPENAI
```

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

1. **OpenAI API Key**: Keep your API key secure, never commit to git
2. **Network Access**: Port 8000 is now accessible from admin_cidr
3. **Authentication**: Currently no auth on dashboard (add if needed)
4. **HTTPS**: Consider adding reverse proxy with SSL/TLS

## Next Steps

- [ ] Add authentication to web dashboard
- [ ] Implement auto-remediation based on approved suggestions
- [ ] Add email/Slack notifications for critical findings
- [ ] Expand scanner to check more OpenStack resources
- [ ] Add historical trends and charts

## Support

For issues or questions, check:
- Container logs: `docker compose logs`
- Application logs: `/data/secops/secops.log`
- Database: `/data/secops/findings.db`








