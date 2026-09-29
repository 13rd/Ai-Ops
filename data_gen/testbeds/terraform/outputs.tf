output "vm_ips" {
  description = "IP addresses of all testbed VMs"
  value = {
    for name, vm in proxmox_vm_qemu.testbed : name => split("/", split("ip=", vm.ipconfig0)[1])[0]
  }
}
