variable "openstack_cloud" {
  description = "Name of the cloud in clouds.yaml"
  type        = string
  default     = "kolla"
}

variable "name_prefix" {
  type    = string
  default = "secops"
}

variable "region" {
  type    = string
  default = null
}

variable "image_name" {
  description = "Image name to boot instances (Glance)"
  type        = string
}

variable "private_vm_image_name" {
  description = "Image name for private VM (defaults to image_name if not specified)"
  type        = string
  default     = null
}

variable "keypair_name" {
  description = "Existing Nova keypair name"
  type        = string
}

variable "admin_cidr" {
  description = "Your public IP/CIDR allowed to SSH/Grafana (e.g., 1.2.3.4/32)"
  type        = string
}

variable "external_network_name" {
  description = "External network name for router gateway & floating IPs (e.g., public)"
  type        = string
}

variable "net_cidr" {
  description = "CIDR for internal secops subnet"
  type        = string
  default     = "10.10.50.0/24"
}

variable "private_net_cidr" {
  description = "CIDR for private VM subnet (a-private-net)"
  type        = string
  default     = "10.10.51.0/24"
}

variable "dns_nameservers" {
  type    = list(string)
  default = ["8.8.8.8", "1.1.1.1"]
}

# Flavor per VM (root disk is from flavor)
variable "flavors" {
  description = "Map of flavors for each VM"
  type        = map(string)
}

# Cinder data volume sizes (GB)
variable "data_volume_sizes" {
  description = "Extra Cinder volume size (GB) for each VM"
  type = object({
    secops_app = number
    obs_stack  = number
    workload   = number
  })
  default = {
    secops_app = 10
    obs_stack  = 20
    workload   = 10
  }
}

variable "enable_fip_obs" {
  description = "Allocate & associate Floating IP to obs-stack (Grafana access)"
  type        = bool
  default     = true
}

variable "enable_fip_app" {
  description = "Optional Floating IP for secops-app"
  type        = bool
  default     = false
}

variable "ssh_user" {
  description = "SSH user for Ansible inventory (e.g., ubuntu, root)"
  type        = string
  default     = "ubuntu"
}

variable "gateway_instance" {
  description = "Instance name to use as gateway/jump host (secops_app, obs_stack, or workload). Defaults to instance with floating IP."
  type        = string
  default     = null
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key file for Ansible"
  type        = string
  default     = "/home/deployer/.ssh/key-b"
}
    