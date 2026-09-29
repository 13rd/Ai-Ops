variable "proxmox_api_url" {
  type        = string
  description = "Proxmox API URL, e.g. https://192.168.1.10:8006/api2/json"
}

variable "proxmox_user" {
  type        = string
  default     = "root@pam"
  description = "Proxmox API user"
}

variable "proxmox_password" {
  type        = string
  sensitive   = true
  description = "Proxmox API password"
}

variable "proxmox_node" {
  type        = string
  default     = "pve"
  description = "Proxmox node name"
}

variable "ubuntu_template" {
  type        = string
  default     = "ubuntu-22.04-cloud"
  description = "Name of the Ubuntu 22.04 cloud-init VM template in Proxmox"
}

variable "storage_pool" {
  type        = string
  default     = "local-lvm"
  description = "Proxmox storage pool for VM disks"
}

variable "gateway" {
  type        = string
  default     = "192.168.10.1"
  description = "Default gateway for testbed VM network"
}

variable "vm_password" {
  type        = string
  sensitive   = true
  default     = "testbed123"
  description = "Password for the ubuntu user on testbed VMs"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key to inject into testbed VMs for ubuntu user"
}
