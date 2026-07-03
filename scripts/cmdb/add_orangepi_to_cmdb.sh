#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${1:-cmdb-netbox}"

echo "🔧 Adicionando Orange Pi Zero 2W ao CMDB..."

docker exec -i "$CONTAINER" /opt/netbox/venv/bin/python3 /opt/netbox/netbox/manage.py shell <<'PYEOF'
from django.utils.text import slugify
from dcim.choices import DeviceStatusChoices, InterfaceTypeChoices
from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Platform, Site
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress, Prefix

# Ensure site exists
site, _ = Site.objects.get_or_create(name='homelab-main', defaults={'slug': slugify('homelab-main')})

# Create/get edge-device role
role, created = DeviceRole.objects.get_or_create(
    name='edge-device',
    defaults={'slug': 'edge-device', 'color': 'ff9800'}
)
if created:
    print(f"  ✅ Criado role: {role.name}")

# Create/get manufacturer
mfr, created = Manufacturer.objects.get_or_create(
    name='Xunlong Orange Pi',
    defaults={'slug': slugify('Xunlong Orange Pi')}
)
if created:
    print(f"  ✅ Criado fabricante: {mfr.name}")

# Create/get device type
dtype, created = DeviceType.objects.get_or_create(
    model='Orange Pi Zero 2W',
    manufacturer=mfr,
    defaults={
        'slug': slugify('Orange Pi Zero 2W'),
        'u_height': 1,
        'is_full_depth': False,
    },
)
if created:
    print(f"  ✅ Criado tipo: {dtype.model}")

# Ensure platform
platform, _ = Platform.objects.get_or_create(name='linux', defaults={'slug': 'linux'})

# Ensure prefix
prefix, _ = Prefix.objects.get_or_create(prefix='192.168.15.0/24', defaults={'status': 'active'})

# Create device
device, created = Device.objects.get_or_create(
    name='orangepizero2w',
    defaults={
        'device_type': dtype,
        'role': role,
        'site': site,
        'platform': platform,
        'status': DeviceStatusChoices.STATUS_ACTIVE,
    },
)

if created:
    print(f"  ✅ Criado device: {device.name}")
else:
    print(f"  ℹ️ Device já existe: {device.name}")
    # Atualizar se necessário
    device.device_type = dtype
    device.role = role
    device.site = site
    device.platform = platform
    device.status = DeviceStatusChoices.STATUS_ACTIVE
    device.save()

# Criar interface eth0
iface, created = Interface.objects.get_or_create(
    device=device,
    name='eth0',
    defaults={'type': InterfaceTypeChoices.TYPE_VIRTUAL}
)
if created:
    print(f"  ✅ Criada interface: {iface.name}")

# Criar IP
ip, created = IPAddress.objects.get_or_create(
    address='192.168.15.166/24',
    defaults={'status': IPAddressStatusChoices.STATUS_ACTIVE}
)
if created:
    print(f"  ✅ Criado IP: {ip.address}")

# Associar IP à interface
if ip.assigned_object != iface:
    ip.assigned_object = iface
    ip.status = IPAddressStatusChoices.STATUS_ACTIVE
    ip.save()
    print(f"  ✅ Associado IP à interface")

# Set primary IP
if device.primary_ip4 != ip:
    device.primary_ip4 = ip
    device.save()
    print(f"  ✅ IP configurado como primário")

print("\n✅ Orange Pi adicionado ao CMDB com sucesso!")
print(f"  • Device: {device.name}")
print(f"  • IP: {ip.address}")
print(f"  • Role: {device.role.name}")
print(f"  • Site: {device.site.name}")
PYEOF

echo "✅ CMDB atualizado!"
