#!/bin/bash
# Script para criar VM Windows 10 no VirtualBox

VM_NAME="Win10PrinterVM"
ISO_PATH="/home/homelab/en-us_windows_10_business_editions_version_22h2_updated_oct_2025_x64_dvd_d2eef4b0.iso"
VMDK_PATH="/home/homelab/${VM_NAME}.vdi"
RAM_MB=4096
CPUS=2

# Cria a VM
VBoxManage createvm --name "$VM_NAME" --ostype Windows10_64 --register

# Configura memória e CPU
VBoxManage modifyvm "$VM_NAME" --memory $RAM_MB --cpus $CPUS --vram 128 --ioapic on --boot1 dvd --nic1 nat

# Cria disco virtual
VBoxManage createmedium disk --filename "$VMDK_PATH" --size 51200 --format VDI
VBoxManage storagectl "$VM_NAME" --name "SATA Controller" --add sata --controller IntelAhci
VBoxManage storageattach "$VM_NAME" --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium "$VMDK_PATH"

# Adiciona controladora IDE para ISO
VBoxManage storagectl "$VM_NAME" --name "IDE Controller" --add ide
VBoxManage storageattach "$VM_NAME" --storagectl "IDE Controller" --port 0 --device 0 --type dvddrive --medium "$ISO_PATH"

# Habilita RDP
VBoxManage modifyvm "$VM_NAME" --vrde on --vrdeport 3389

# Inicia a VM em modo headless
VBoxManage startvm "$VM_NAME" --type headless

echo "VM criada e iniciada. Acesse via RDP em <IP_DO_SERVIDOR>:3389"
