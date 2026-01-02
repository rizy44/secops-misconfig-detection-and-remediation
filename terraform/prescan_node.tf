# ============================================================
# Pre-Scan Node VM Resources
# ============================================================
# This file should be included in the main terraform configuration
# or can be used as a separate module

# Pre-Scan Node Security Group
resource "openstack_networking_secgroup_v2" "prescan_sg" {
  name        = "secops-sg-prescan"
  description = "Security group for Pre-Scan Node"
}

# Allow SSH from admin CIDR
resource "openstack_networking_secgroup_rule_v2" "prescan_ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.admin_cidr
  security_group_id = openstack_networking_secgroup_v2.prescan_sg.id
}

# Allow API access from internal network
resource "openstack_networking_secgroup_rule_v2" "prescan_api" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8001
  port_range_max    = 8001
  remote_ip_prefix  = var.tenant_cidr
  security_group_id = openstack_networking_secgroup_v2.prescan_sg.id
}

# Allow outbound
resource "openstack_networking_secgroup_rule_v2" "prescan_egress" {
  direction         = "egress"
  ethertype         = "IPv4"
  security_group_id = openstack_networking_secgroup_v2.prescan_sg.id
}

# Pre-Scan Node Volume
resource "openstack_blockstorage_volume_v3" "prescan_data" {
  name        = "prescan-data"
  description = "Data volume for Pre-Scan Node"
  size        = var.prescan_volume_size
}

# Pre-Scan Node Port
resource "openstack_networking_port_v2" "prescan_port" {
  name               = "prescan-node-port"
  network_id         = openstack_networking_network_v2.tenant_net.id
  admin_state_up     = true
  security_group_ids = [openstack_networking_secgroup_v2.prescan_sg.id]

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.tenant_subnet.id
    ip_address = var.prescan_ip
  }
}

# Pre-Scan Node Instance
resource "openstack_compute_instance_v2" "prescan_node" {
  name            = "prescan-node"
  image_name      = var.image_name
  flavor_name     = var.flavors.prescan_node
  key_pair        = var.keypair_name
  security_groups = [openstack_networking_secgroup_v2.prescan_sg.name]

  network {
    port = openstack_networking_port_v2.prescan_port.id
  }

  metadata = {
    role        = "prescan-node"
    environment = var.environment
    managed_by  = "terraform"
  }

  user_data = templatefile("${path.module}/templates/prescan_cloud_init.yml", {
    prescan_ip    = var.prescan_ip
    secops_app_ip = var.secops_app_ip
    admin_cidr    = var.admin_cidr
    tenant_cidr   = var.tenant_cidr
  })
}

# Attach data volume
resource "openstack_compute_volume_attach_v2" "prescan_data_attach" {
  instance_id = openstack_compute_instance_v2.prescan_node.id
  volume_id   = openstack_blockstorage_volume_v3.prescan_data.id
}

# Variables for Pre-Scan Node
variable "prescan_ip" {
  description = "Fixed IP for Pre-Scan Node"
  type        = string
  default     = "10.10.50.100"
}

variable "prescan_volume_size" {
  description = "Size of data volume in GB"
  type        = number
  default     = 20
}

# Outputs
output "prescan_node_ip" {
  description = "Internal IP of Pre-Scan Node"
  value       = openstack_compute_instance_v2.prescan_node.access_ip_v4
}

output "prescan_node_id" {
  description = "Instance ID of Pre-Scan Node"
  value       = openstack_compute_instance_v2.prescan_node.id
}
