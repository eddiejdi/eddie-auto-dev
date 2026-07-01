#!/usr/bin/env bash

set -euo pipefail

USAGE="Usage: $0 [--container NAME]

Seeds a minimal NetBox inventory with the homelab site, one device, one
management interface, one /24 prefix and the primary IPv4 address."

CONTAINER="cmdb-netbox"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container) CONTAINER="$2"; shift 2 ;;
    -h|--help) printf '%s\n' "$USAGE"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; printf '%s\n' "$USAGE" >&2; exit 2 ;;
  esac
done

docker exec -i "$CONTAINER" /opt/netbox/venv/bin/python3 /opt/netbox/netbox/manage.py shell <<'PY'
from django.utils.text import slugify
from dcim.choices import DeviceStatusChoices, InterfaceTypeChoices
from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Platform, Site
from ipam.choices import IPAddressStatusChoices
from ipam.models import IPAddress, Prefix

site, _ = Site.objects.get_or_create(name='homelab-main', defaults={'slug': slugify('homelab-main')})
role, _ = DeviceRole.objects.get_or_create(name='compute-node', defaults={'slug': slugify('compute-node'), 'color': '9e9e9e'})
mfr, _ = Manufacturer.objects.get_or_create(name='RPA4All', defaults={'slug': slugify('RPA4All')})
dtype, _ = DeviceType.objects.get_or_create(
    model='Generic Linux Host',
    manufacturer=mfr,
    defaults={'slug': slugify('Generic Linux Host'), 'u_height': 1, 'is_full_depth': False},
)
platform, _ = Platform.objects.get_or_create(name='linux', defaults={'slug': 'linux'})
prefix, _ = Prefix.objects.get_or_create(prefix='192.168.15.0/24', defaults={'status': 'active'})
device, created = Device.objects.get_or_create(
    name='homelab',
    defaults={
        'device_type': dtype,
        'role': role,
        'site': site,
        'platform': platform,
        'status': DeviceStatusChoices.STATUS_ACTIVE,
    },
)
if not created:
    device.device_type = dtype
    device.role = role
    device.site = site
    device.platform = platform
    device.status = DeviceStatusChoices.STATUS_ACTIVE
    device.save()
iface, _ = Interface.objects.get_or_create(device=device, name='mgmt0', defaults={'type': InterfaceTypeChoices.TYPE_VIRTUAL})
ip, _ = IPAddress.objects.get_or_create(address='192.168.15.2/24', defaults={'status': IPAddressStatusChoices.STATUS_ACTIVE})
ip.assigned_object = iface
ip.status = IPAddressStatusChoices.STATUS_ACTIVE
ip.save()
device.primary_ip4 = ip
device.save()
print({'device': device.name, 'interface': iface.name, 'ip': str(ip.address), 'prefix': str(prefix.prefix)})
PY
