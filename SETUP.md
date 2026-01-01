# Setup Instructions

This guide will help you set up the SecOps platform from scratch.

## Prerequisites

Before you begin, ensure you have:

- **OpenStack Cloud**: Access to an OpenStack cloud with:
  - `clouds.yaml` configured (`~/.config/openstack/clouds.yaml`)
  - Ubuntu 22.04 image available in Glance
  - SSH keypair created in OpenStack
  - External network (e.g., `public1`) available
  - Required flavors created
  - Sufficient quota (3-4 VMs, 3 volumes, 2+ floating IPs)

- **Tools Installed**:
  - Terraform >= 1.3.0
  - Ansible >= 2.9
  - OpenStack CLI (`python-openstackclient`)
  - SSH client
  - Python 3.8+

## Step 1: Configure OpenStack Credentials

### For SecOps App (OpenStack API Access)

Copy the example OpenRC file and configure with your credentials:

```bash
cd ansible/files/
cp tenantA-openrc.sh.example tenantA-openrc.sh
```

Edit `tenantA-openrc.sh`:

```bash
export OS_PROJECT_NAME='your-project'
export OS_USERNAME='your-username'
export OS_PASSWORD='your-password'
export OS_AUTH_URL='http://YOUR_OPENSTACK_IP:5000/v3'
export OS_REGION_NAME='RegionOne'
```

**Important**: This file contains sensitive credentials. Never commit it to git!

## Step 2: Configure Terraform Variables

Copy the example tfvars file:

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
openstack_cloud         = "kolla"              # Name from clouds.yaml
image_name              = "Ubuntu-22.04"       # Your image name
keypair_name            = "your-keypair"       # Your SSH keypair
admin_cidr              = "YOUR_IP/32"         # Your public IP for access
ssh_private_key_path    = "/path/to/your/key" # Path to SSH private key

# Adjust flavors if needed
flavors = {
  secops_app = "flavor-secops-app"
  obs_stack  = "flavor-obs-stack"
  gateway    = "flavor-workload"
  private_vm = "flavor-workload"
}
```

**Note**: `admin_cidr` should be your public IP or the IP range you'll access from.

## Step 3: Deploy Infrastructure

```bash
cd terraform/

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Deploy infrastructure
terraform apply

# Terraform will automatically generate ansible/inventory.ini
```

After successful deployment, note the outputs:
- `gateway_floating_ip`: Use this to SSH into the environment
- `obs_stack_floating_ip`: Use this to access Grafana

## Step 4: Verify Inventory

The inventory file is automatically generated at `ansible/inventory.ini`.

Verify connectivity:

```bash
cd ../ansible/

# Test SSH connectivity
ansible all -i inventory.ini -m ping
```

If the ping fails, check:
- Security groups allow SSH from your IP
- Floating IP is accessible
- SSH key permissions (`chmod 600 /path/to/key`)

## Step 5: Deploy Services

Run playbooks in order:

```bash
# 1. Mount data volumes
ansible-playbook -i inventory.ini 00-mount-data.yml

# 2. Install Docker
ansible-playbook -i inventory.ini 01-docker.yml

# 3. Deploy Observability Stack
ansible-playbook -i inventory.ini 02-obs-stack.yml

# 4. Deploy Monitoring Agents
ansible-playbook -i inventory.ini 03-agents.yml

# 5. Deploy SecOps App
ansible-playbook -i inventory.ini 04-secops-app.yml

# 6. Configure Gateway Routing
ansible-playbook -i inventory.ini 05-gateway-routing.yml

# 7. (Optional) Verify everything
ansible-playbook -i inventory.ini 99-verify-all.yml
```

Or run all at once:

```bash
ansible-playbook -i inventory.ini \
  00-mount-data.yml \
  01-docker.yml \
  02-obs-stack.yml \
  03-agents.yml \
  04-secops-app.yml \
  05-gateway-routing.yml
```

## Step 6: Access the System


### Grafana Dashboard

1. Get the Obs Stack floating IP:
   ```bash
   cd terraform
   terraform output obs_stack_floating_ip
   ```

2. Open in browser:
   ```
   http://<obs-floating-ip>:3000
   ```

3. Login:
   - Username: `admin`
   - Password: `admin` (change on first login)

4. Add Data Sources:
   - **Prometheus**: URL = `http://localhost:9090`
   - **Loki**: URL = `http://localhost:3100`

### SecOps CLI

```bash
# SSH into secops-app container
docker exec -it secops-secops-app-1 bash

# Use CLI
secops-cli findings list
secops-cli scan
secops-cli remediate run <finding-id> --force
```


### SecOps API

```bash
# From local machine (via SSH tunnel)
ssh -L 8000:10.10.50.237:8000 ubuntu@<gateway-floating-ip>

# In another terminal
curl http://localhost:8000/api/findings
```

## Troubleshooting

### Cannot SSH to gateway

Check security group rules:
```bash
openstack security group rule list secops-sg-ssh-admin
```

Ensure your IP is in `admin_cidr`.

### Terraform apply fails

Common issues:
- Flavor doesn't exist: Update flavors in `terraform.tfvars`
- Image not found: Check image name in Glance
- Quota exceeded: Request quota increase or reduce resources
- Keypair not found: Create keypair in OpenStack

### Ansible playbook fails

- Verify inventory: `ansible all -i inventory.ini -m ping`
- Check SSH key permissions: `chmod 600 /path/to/key`
- Increase timeout if slow: Add `-T 60` to ansible command

### SecOps not scanning

1. Check OpenStack credentials:
   ```bash
   docker exec -it secops-secops-app-1 bash
   cat /opt/secops/secops_app/openstack.env
   ```

2. Check logs:
   ```bash
   docker logs secops-secops-app-1
   tail -f /data/secops/secops.log
   ```

3. Test OpenStack connection:
   ```bash
   source /opt/secops/tenantA-openrc.sh
   openstack server list
   ```

## Security Best Practices

1. **Never commit credentials**:
   - `.gitignore` is configured to exclude sensitive files
   - Always use `.example` files in repository

2. **Restrict admin_cidr**:
   - Use specific IP (`YOUR_IP/32`) instead of broad ranges
   - Update security groups if your IP changes

3. **Change default passwords**:
   - Grafana admin password (first login)
   - Any other default credentials

4. **Use SSH keys only**:
   - Disable password authentication
   - Use strong SSH keys (ED25519 or RSA 4096)

5. **Regular updates**:
   - Keep images updated
   - Apply security patches
   - Monitor CVEs for dependencies

## Next Steps

- Read the main [README.md](README.md) for usage instructions
- Check [ASSET/](ASSET/) directory for detailed architecture documentation
- Review findings and create remediation workflows
- Configure alerting in Grafana

## Cleanup

To destroy all resources:

```bash
cd terraform/
terraform destroy
```

**Warning**: This will delete all VMs, volumes, and data. Make sure to backup important data first!

