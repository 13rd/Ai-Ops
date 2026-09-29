terraform {
  required_providers {
    proxmox = {
      source  = "Telmate/proxmox"
      version = "~> 2.9"
    }
  }
}

provider "proxmox" {
  pm_api_url      = var.proxmox_api_url
  pm_user         = var.proxmox_user
  pm_password     = var.proxmox_password
  pm_tls_insecure = true
}

locals {
  vms = {
    "testbed-normal-1" = {
      cores   = 2
      memory  = 4096
      disk_gb = 20
      ip      = "192.168.10.101"
      ci_file = "vm-normal-1.yaml"
      vmid    = 201
    }
    "testbed-normal-2" = {
      cores   = 4
      memory  = 8192
      disk_gb = 30
      ip      = "192.168.10.102"
      ci_file = "vm-normal-2.yaml"
      vmid    = 202
    }
    "testbed-anomaly-mem" = {
      cores   = 4
      memory  = 16384
      disk_gb = 30
      ip      = "192.168.10.103"
      ci_file = "vm-anomaly-mem.yaml"
      vmid    = 203
    }
    "testbed-anomaly-net" = {
      cores   = 2
      memory  = 4096
      disk_gb = 20
      ip      = "192.168.10.104"
      ci_file = "vm-anomaly-net.yaml"
      vmid    = 204
    }
  }
}

resource "proxmox_vm_qemu" "testbed" {
  for_each    = local.vms
  name        = each.key
  vmid        = each.value.vmid
  target_node = var.proxmox_node
  clone       = var.ubuntu_template
  os_type     = "cloud-init"
  cores       = each.value.cores
  sockets     = 1
  memory      = each.value.memory
  agent       = 1
  onboot      = true

  disk {
    slot    = "scsi0"
    size    = "${each.value.disk_gb}G"
    type    = "scsi"
    storage = var.storage_pool
    ssd     = 1
  }

  network {
    model  = "virtio"
    bridge = "vmbr0"
  }

  ipconfig0  = "ip=${each.value.ip}/24,gw=${var.gateway}"
  nameserver = "8.8.8.8"
  ciuser     = "ubuntu"
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key
  cicustom   = "user=local:snippets/${each.value.ci_file}"

  lifecycle {
    ignore_changes = [network, disk]
  }
}
