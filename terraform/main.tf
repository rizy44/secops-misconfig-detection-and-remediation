# ============================================================================
# Data Sources
# ============================================================================

data "openstack_images_image_v2" "img" {
  name        = var.image_name
  most_recent = true
}

data "openstack_images_image_v2" "private_vm_img" {
  name        = var.private_vm_image_name != null ? var.private_vm_image_name : var.image_name
  most_recent = true
}

data "openstack_networking_network_v2" "external" {
  name = var.external_network_name
}

# ============================================================================
# Network Resources
# ============================================================================

resource "openstack_networking_network_v2" "secops_net" {
  name = "${var.name_prefix}-net"
}

resource "openstack_networking_subnet_v2" "secops_subnet" {
  name            = "${var.name_prefix}-subnet"
  network_id      = openstack_networking_network_v2.secops_net.id
  cidr            = var.net_cidr
  ip_version      = 4
  dns_nameservers = var.dns_nameservers
}

resource "openstack_networking_router_v2" "secops_router" {
  name                = "${var.name_prefix}-router"
  external_network_id  = data.openstack_networking_network_v2.external.id
}

resource "openstack_networking_router_interface_v2" "secops_router_if" {
  router_id = openstack_networking_router_v2.secops_router.id
  subnet_id = openstack_networking_subnet_v2.secops_subnet.id
}

# ============================================================================
# Security Groups
# ============================================================================

# SSH admin - Allow SSH from admin_cidr and from subnet (for testing and gateway access)
resource "openstack_networking_secgroup_v2" "sg_ssh_admin" {
  name        = "${var.name_prefix}-sg-ssh-admin"
  description = "Allow SSH from admin_cidr and subnet (for testing)"
}

resource "openstack_networking_secgroup_rule_v2" "sg_ssh_admin_22" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.admin_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_ssh_admin.id
}

resource "openstack_networking_secgroup_rule_v2" "sg_ssh_from_subnet" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_ssh_admin.id
  description       = "Allow SSH from subnet for testing and gateway access"
}

# Obs public: Grafana dashboard access
resource "openstack_networking_secgroup_v2" "sg_obs_public" {
  name        = "${var.name_prefix}-sg-obs-public"
  description = "Allow Grafana dashboard from admin_cidr and subnet"
}

# Grafana (3000) from admin CIDR (via floating IP)
resource "openstack_networking_secgroup_rule_v2" "sg_obs_grafana_admin" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3000
  port_range_max    = 3000
  remote_ip_prefix  = var.admin_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_obs_public.id
  description       = "Allow Grafana from admin CIDR (for dashboard access via floating IP)"
}

# Grafana (3000) from subnet (for internal access)
resource "openstack_networking_secgroup_rule_v2" "sg_obs_grafana_subnet" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3000
  port_range_max    = 3000
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_obs_public.id
  description       = "Allow Grafana from subnet (for internal access)"
}

# Internal traffic within subnet for observability + secops
resource "openstack_networking_secgroup_v2" "sg_internal" {
  name        = "${var.name_prefix}-sg-internal"
  description = "Allow internal ports within secops subnet"
}

# ICMP (ping) from subnet - Allow ping for connectivity testing
resource "openstack_networking_secgroup_rule_v2" "internal_icmp" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
  description       = "Allow ICMP ping from subnet for connectivity testing"
}

# ICMP (ping) from admin_cidr
resource "openstack_networking_secgroup_rule_v2" "internal_icmp_admin" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  remote_ip_prefix  = var.admin_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
  description       = "Allow ICMP ping from admin CIDR"
}

# Loki (3100) inbound from subnet
resource "openstack_networking_secgroup_rule_v2" "internal_loki" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3100
  port_range_max    = 3100
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
}

# Prometheus (9090) inbound from subnet
resource "openstack_networking_secgroup_rule_v2" "internal_prometheus" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9090
  port_range_max    = 9090
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
}

# Node Exporter (9100) inbound from subnet
resource "openstack_networking_secgroup_rule_v2" "internal_node_exporter" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 9100
  port_range_max    = 9100
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
}

# Secops API (8000) inbound from subnet
resource "openstack_networking_secgroup_rule_v2" "internal_secops_api" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8000
  port_range_max    = 8000
  remote_ip_prefix  = var.net_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
}

# Secops API (8000) inbound from admin_cidr for web dashboard access
resource "openstack_networking_secgroup_rule_v2" "internal_secops_api_admin" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 8000
  port_range_max    = 8000
  remote_ip_prefix  = var.admin_cidr
  security_group_id = openstack_networking_secgroup_v2.sg_internal.id
  description       = "Allow SecOps web dashboard from admin CIDR"
}

# ============================================================================
# Private Network (for testing scan findings)
# ============================================================================

resource "openstack_networking_network_v2" "a_private_net" {
  name = "${var.name_prefix}-a-private-net"
}

resource "openstack_networking_subnet_v2" "a_subnet_private" {
  name            = "${var.name_prefix}-a-subnet-private"
  network_id      = openstack_networking_network_v2.a_private_net.id
  cidr            = var.private_net_cidr
  ip_version      = 4
  dns_nameservers = var.dns_nameservers
}

# Router chỉ nối tới secops-net, không nối tới a-private-net
# Gateway sẽ route traffic giữa 2 mạng
resource "openstack_networking_router_interface_v2" "private_router_if" {
  router_id = openstack_networking_router_v2.secops_router.id
  subnet_id = openstack_networking_subnet_v2.a_subnet_private.id
}

# ============================================================================
# Security Groups for Private VM (with misconfigurations for testing)
# ============================================================================

resource "openstack_networking_secgroup_v2" "sg_private_vm_test" {
  name        = "${var.name_prefix}-sg-private-vm-test"
  description = "Security group với các misconfigurations để test scanner"
}

# SSH mở to world (để test SG_WORLD_OPEN_SSH)
resource "openstack_networking_secgroup_rule_v2" "sg_private_vm_ssh_world" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "${var.admin_cidr}"
  security_group_id = openstack_networking_secgroup_v2.sg_private_vm_test.id
  description       = "Intentionally insecure: SSH open to world for testing"
}

# RDP mở to world (để test SG_WORLD_OPEN_RDP)
resource "openstack_networking_secgroup_rule_v2" "sg_private_vm_rdp_world" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3389
  port_range_max    = 3389
  remote_ip_prefix  = "${var.admin_cidr}"
  security_group_id = openstack_networking_secgroup_v2.sg_private_vm_test.id
  description       = "Intentionally insecure: RDP open to world for testing"
}

# MySQL mở to world (để test SG_WORLD_OPEN_DB_PORT)
resource "openstack_networking_secgroup_rule_v2" "sg_private_vm_mysql_world" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 3306
  port_range_max    = 3306
  remote_ip_prefix  = "${var.admin_cidr}"
  security_group_id = openstack_networking_secgroup_v2.sg_private_vm_test.id
  description       = "Intentionally insecure: MySQL open to world for testing"
}

# ============================================================================
# Ports
# ============================================================================

resource "openstack_networking_port_v2" "port_app" {
  name       = "${var.name_prefix}-port-secops-app"
  network_id = openstack_networking_network_v2.secops_net.id

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.secops_subnet.id
  }

  security_group_ids = [
    openstack_networking_secgroup_v2.sg_ssh_admin.id,
    openstack_networking_secgroup_v2.sg_internal.id
  ]

  depends_on = [openstack_networking_subnet_v2.secops_subnet]
}

resource "openstack_networking_port_v2" "port_obs" {
  name       = "${var.name_prefix}-port-obs-stack"
  network_id = openstack_networking_network_v2.secops_net.id

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.secops_subnet.id
  }

  security_group_ids = [
    openstack_networking_secgroup_v2.sg_ssh_admin.id,
    openstack_networking_secgroup_v2.sg_internal.id,
    openstack_networking_secgroup_v2.sg_obs_public.id
  ]

  depends_on = [openstack_networking_subnet_v2.secops_subnet]
}

# Gateway port on secops-net
resource "openstack_networking_port_v2" "port_gateway_secops" {
  name       = "${var.name_prefix}-port-gateway-secops"
  network_id = openstack_networking_network_v2.secops_net.id

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.secops_subnet.id
  }

  security_group_ids = [
    openstack_networking_secgroup_v2.sg_ssh_admin.id,
    openstack_networking_secgroup_v2.sg_internal.id
  ]

  depends_on = [openstack_networking_subnet_v2.secops_subnet]
}

# Gateway port on private network (dual-homed)
resource "openstack_networking_port_v2" "port_gateway_private" {
  name       = "${var.name_prefix}-port-gateway-private"
  network_id = openstack_networking_network_v2.a_private_net.id

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.a_subnet_private.id
  }

  security_group_ids = [
    openstack_networking_secgroup_v2.sg_ssh_admin.id
  ]

  depends_on = [openstack_networking_subnet_v2.a_subnet_private]
}

# Port với port_security_enabled = true (để test PORT_SECURITY_DISABLED)
# Lưu ý: Khi port_security_enabled = true, không thể dùng security groups
resource "openstack_networking_port_v2" "port_private_vm" {
  name                 = "${var.name_prefix}-port-private-vm"
  network_id           = openstack_networking_network_v2.a_private_net.id
  port_security_enabled = true  # Misconfiguration để test

  fixed_ip {
    subnet_id = openstack_networking_subnet_v2.a_subnet_private.id
  }

  # Không thể dùng security_group_ids khi port_security_enabled = true
  # Security groups sẽ được apply ở instance level nếu cần

  depends_on = [openstack_networking_subnet_v2.a_subnet_private]
}

# ============================================================================
# Compute Instances
# ============================================================================

resource "openstack_compute_instance_v2" "secops_app" {
  name        = "${var.name_prefix}-secops-app"
  image_id    = data.openstack_images_image_v2.img.id
  flavor_name = var.flavors["secops_app"]
  key_pair    = var.keypair_name

  network {
    port = openstack_networking_port_v2.port_app.id
  }

  depends_on = [openstack_networking_router_interface_v2.secops_router_if]
}

# Obs stack instance (chỉ thu thập log/metrics, không phải gateway)
resource "openstack_compute_instance_v2" "obs_stack" {
  name        = "${var.name_prefix}-obs-stack"
  image_id    = data.openstack_images_image_v2.img.id
  flavor_name = var.flavors["obs_stack"]
  key_pair    = var.keypair_name

  network {
    port = openstack_networking_port_v2.port_obs.id
  }

  depends_on = [openstack_networking_router_interface_v2.secops_router_if]
}

# Gateway instance (dual-homed: secops-net + a-private-net)
resource "openstack_compute_instance_v2" "gateway" {
  name        = "${var.name_prefix}-gateway"
  image_id    = data.openstack_images_image_v2.img.id
  flavor_name = var.flavors["gateway"]
  key_pair    = var.keypair_name

  network {
    port = openstack_networking_port_v2.port_gateway_secops.id
  }

  network {
    port = openstack_networking_port_v2.port_gateway_private.id
  }

  depends_on = [
    openstack_networking_router_interface_v2.secops_router_if
  ]
}

# Private VM for testing scan findings
resource "openstack_compute_instance_v2" "private_vm" {
  name        = "${var.name_prefix}-private-vm"
  image_id    = data.openstack_images_image_v2.private_vm_img.id
  flavor_name = var.flavors["private_vm"]
  key_pair    = var.keypair_name

  network {
    port = openstack_networking_port_v2.port_private_vm.id
  }
}

# ============================================================================
# Floating IPs
# ============================================================================

resource "openstack_networking_floatingip_v2" "fip_obs" {
  count = var.enable_fip_obs ? 1 : 0
  pool  = var.external_network_name

  depends_on = [openstack_networking_router_interface_v2.secops_router_if]
}

resource "openstack_networking_floatingip_associate_v2" "fip_obs_assoc" {
  count       = var.enable_fip_obs ? 1 : 0
  floating_ip = openstack_networking_floatingip_v2.fip_obs[0].address
  port_id     = openstack_networking_port_v2.port_obs.id

  depends_on = [
    openstack_networking_router_interface_v2.secops_router_if,
    openstack_compute_instance_v2.obs_stack
  ]
}

# Floating IP cho gateway (để SSH vào từ bên ngoài)
resource "openstack_networking_floatingip_v2" "fip_gateway" {
  pool  = var.external_network_name

  depends_on = [openstack_networking_router_interface_v2.secops_router_if]
}

resource "openstack_networking_floatingip_associate_v2" "fip_gateway_assoc" {
  floating_ip = openstack_networking_floatingip_v2.fip_gateway.address
  port_id     = openstack_networking_port_v2.port_gateway_secops.id

  depends_on = [
    openstack_networking_router_interface_v2.secops_router_if,
    openstack_compute_instance_v2.gateway
  ]
}

# Private VM không có FIP - nó phải thực sự private, chỉ accessible qua gateway

resource "openstack_networking_floatingip_v2" "fip_app" {
  count = var.enable_fip_app ? 1 : 0
  pool  = var.external_network_name

  depends_on = [openstack_networking_router_interface_v2.secops_router_if]
}

resource "openstack_networking_floatingip_associate_v2" "fip_app_assoc" {
  count       = var.enable_fip_app ? 1 : 0
  floating_ip = openstack_networking_floatingip_v2.fip_app[0].address
  port_id     = openstack_networking_port_v2.port_app.id

  depends_on = [
    openstack_networking_router_interface_v2.secops_router_if,
    openstack_compute_instance_v2.secops_app
  ]
}

# ============================================================================
# Block Storage Volumes - DISABLED: Using root disk from flavor instead
# ============================================================================

# Volumes are no longer used. Data is stored on root disk from flavor.
# Ensure flavors have sufficient disk size:
#   - secops_app: >= 20GB
#   - obs_stack: >= 40GB (for Prometheus, Loki, Grafana data)
#   - workload: >= 10GB

# resource "openstack_blockstorage_volume_v3" "vol_app_data" {
#   name = "${var.name_prefix}-vol-secops-app-data"
#   size = var.data_volume_sizes.secops_app
# }

# resource "openstack_blockstorage_volume_v3" "vol_obs_data" {
#   name = "${var.name_prefix}-vol-obs-data"
#   size = var.data_volume_sizes.obs_stack
# }

# resource "openstack_blockstorage_volume_v3" "vol_workload_data" {
#   name = "${var.name_prefix}-vol-workload-data"
#   size = var.data_volume_sizes.workload
# }

# # Attach data volume to secops_app
# resource "openstack_compute_volume_attach_v2" "attach_app" {
#   instance_id = openstack_compute_instance_v2.secops_app.id
#   volume_id   = openstack_blockstorage_volume_v3.vol_app_data.id
#   depends_on = [
#     openstack_compute_instance_v2.secops_app,
#     openstack_blockstorage_volume_v3.vol_app_data,
#     openstack_networking_port_v2.port_app
#   ]
# }

# resource "openstack_compute_volume_attach_v2" "attach_obs" {
#   instance_id = openstack_compute_instance_v2.obs_stack.id
#   volume_id   = openstack_blockstorage_volume_v3.vol_obs_data.id
#   depends_on = [
#     openstack_compute_instance_v2.obs_stack,
#     openstack_blockstorage_volume_v3.vol_obs_data,
#     openstack_networking_port_v2.port_obs
#   ]
# }

# # Attach data volume to workload
# resource "openstack_compute_volume_attach_v2" "attach_workload" {
#   instance_id = openstack_compute_instance_v2.workload.id
#   volume_id   = openstack_blockstorage_volume_v3.vol_workload_data.id
#   depends_on = [
#     openstack_compute_instance_v2.workload,
#     openstack_blockstorage_volume_v3.vol_workload_data,
#     openstack_networking_port_v2.port_workload
#   ]
# }

# ============================================================================
# Ansible Inventory Generation
# ============================================================================

locals {
  # Gateway is separate instance
  gateway_instance = "gateway"

  # Get gateway IP (prefer floating IP, fallback to fixed IP on secops-net)
  gateway_ip = openstack_networking_floatingip_v2.fip_gateway.address

  # Get all fixed IPs
  secops_app_ip = try(openstack_networking_port_v2.port_app.all_fixed_ips[0], "")
  obs_stack_ip  = try(openstack_networking_port_v2.port_obs.all_fixed_ips[0], "")
  gateway_secops_ip = try(openstack_networking_port_v2.port_gateway_secops.all_fixed_ips[0], "")
  gateway_private_ip = try(openstack_networking_port_v2.port_gateway_private.all_fixed_ips[0], "")
  private_vm_ip = try(openstack_networking_port_v2.port_private_vm.all_fixed_ips[0], "")
}

resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/templates/inventory.ini.tpl", {
    ssh_user             = var.ssh_user
    gateway_ip           = local.gateway_ip
    gateway_instance     = local.gateway_instance
    secops_app_ip        = local.secops_app_ip
    obs_stack_ip         = local.obs_stack_ip
    gateway_secops_ip    = local.gateway_secops_ip
    gateway_private_ip   = local.gateway_private_ip
    private_vm_ip        = local.private_vm_ip
    name_prefix          = var.name_prefix
    ssh_private_key_path = var.ssh_private_key_path
  })
  filename             = "${path.module}/../ansible/inventory.ini"
  file_permission      = "0644"
  directory_permission = "0755"
}

