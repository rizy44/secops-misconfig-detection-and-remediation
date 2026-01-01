# Instance access IPs
output "secops_app_fixed_ip" {
  value       = openstack_compute_instance_v2.secops_app.access_ip_v4
  description = "Access IP for secops_app instance"
}

output "obs_stack_fixed_ip" {
  value       = openstack_compute_instance_v2.obs_stack.access_ip_v4
  description = "Access IP for obs_stack instance"
}

output "private_vm_fixed_ip" {
  value       = openstack_compute_instance_v2.private_vm.access_ip_v4
  description = "Access IP for private-vm instance"
}

# Floating IPs
output "obs_stack_floating_ip" {
  value       = var.enable_fip_obs ? openstack_networking_floatingip_v2.fip_obs[0].address : null
  description = "Floating IP for obs_stack (use this to access Grafana on port 3000)"
}

output "gateway_floating_ip" {
  value       = openstack_networking_floatingip_v2.fip_gateway.address
  description = "Floating IP for gateway (jump host for SSH access)"
}

output "secops_app_floating_ip" {
  value       = var.enable_fip_app ? openstack_networking_floatingip_v2.fip_app[0].address : null
  description = "Floating IP for secops_app (optional)"
}

# Fixed IPs from ports (more reliable than access_ip_v4)
output "port_app_fixed_ip" {
  value       = try(openstack_networking_port_v2.port_app.all_fixed_ips[0], null)
  description = "Fixed IP from port for secops_app"
}

output "port_obs_fixed_ip" {
  value       = try(openstack_networking_port_v2.port_obs.all_fixed_ips[0], null)
  description = "Fixed IP from port for obs_stack"
}

output "port_gateway_secops_fixed_ip" {
  value       = try(openstack_networking_port_v2.port_gateway_secops.all_fixed_ips[0], null)
  description = "Fixed IP from port for gateway on secops-net"
}

output "port_private_vm_fixed_ip" {
  value       = try(openstack_networking_port_v2.port_private_vm.all_fixed_ips[0], null)
  description = "Fixed IP from port for private-vm"
}

output "gateway_private_ip" {
  value       = try(openstack_networking_port_v2.port_gateway_private.all_fixed_ips[0], null)
  description = "Gateway IP on private network (a-private-net)"
}

# Gateway information
output "gateway_ip" {
  value       = local.gateway_ip
  description = "Gateway IP address (floating IP if available, otherwise fixed IP)"
}

output "gateway_instance" {
  value       = local.gateway_instance
  description = "Instance name used as gateway/jump host"
}

# Ansible inventory
output "ansible_inventory_path" {
  value       = local_file.ansible_inventory.filename
  description = "Path to generated Ansible inventory file"
}
