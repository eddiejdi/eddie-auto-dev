#!/usr/bin/env python3
"""Patch Home Assistant's built-in Tuya integration to refresh online flags.

The upstream `tuya_sharing` cache can return devices with correct status payloads
but stale `online=False`. Home Assistant's Tuya entities use `device.online`
directly for availability, so those devices become `unavailable` even when
`/v1.0/m/life/ha/devices/detail` reports them as online.

This helper patches the Tuya integration inside the running `homeassistant`
container to refresh `device.online` and `device.status` from `devices/detail`
immediately after `manager.update_device_cache()`.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import textwrap


PATCH_SCRIPT = textwrap.dedent(
    """
    import pathlib
    import time

    path = pathlib.Path("/usr/src/homeassistant/homeassistant/components/tuya/__init__.py")
    source = path.read_text()
    backup = path.with_name(path.name + f".bak-{int(time.time())}")
    backup.write_text(source)

    helper = '''

    def _refresh_device_online_flags(manager: Manager) -> None:
        device_ids = list(manager.device_map)
        if not device_ids:
            return

        for idx in range(0, len(device_ids), 50):
            chunk = device_ids[idx : idx + 50]
            try:
                response = manager.customer_api.get(
                    "/v1.0/m/life/ha/devices/detail",
                    {"devIds": ",".join(chunk)},
                )
            except Exception as exc:
                LOGGER.debug(
                    "devices/detail refresh failed for Tuya online flags: %s",
                    exc,
                )
                return

            for item in response.get("result", []):
                device = manager.device_map.get(item.get("id"))
                if device is None:
                    continue
                if "online" in item:
                    device.online = bool(item["online"])
                status_items = item.get("status") or []
                if status_items:
                    device.status = {
                        entry["code"]: entry["value"]
                        for entry in status_items
                        if "code" in entry and "value" in entry
                    }
    '''

    marker = "async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:\\n"
    call = "        await hass.async_add_executor_job(_refresh_device_online_flags, manager)\\n"
    needle = "        await hass.async_add_executor_job(manager.update_device_cache)\\n"

    if helper not in source:
        source = source.replace(marker, helper + "\\n" + marker, 1)
    if call not in source:
        source = source.replace(needle, needle + call, 1)

    path.write_text(source)
    print(backup)
    """
).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="homelab")
    parser.add_argument("--container", default="homeassistant")
    args = parser.parse_args()

    proc = subprocess.run(
        [
            "ssh",
            args.host,
            f"docker exec -i {args.container} python3 -",
        ],
        input=PATCH_SCRIPT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout)
        return proc.returncode

    sys.stdout.write(proc.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
