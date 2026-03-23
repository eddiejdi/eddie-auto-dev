# NAS OMV + LTO Install Guide

## Use This Order

1. Disconnect all data disks before installing the operating system.
2. Leave only the target `NVMe` connected for the OS install.
3. Boot from the Ventoy pendrive.
4. If `openmediavault_8.0-12-amd64.iso` is present on the pendrive, try it first.
5. Otherwise boot `debian-13.4.0-amd64-netinst.iso` and use the OMV post-install script.
6. If the target machine needs a cleaner `UEFI` path, prefer the Debian path.

## Path A: OMV ISO

Use this when the machine boots the OMV installer cleanly.

After install:
- Log in on the console
- Configure static networking if needed
- Access the OMV web UI
- Reconnect the data HDDs
- Build the storage array and shared folders

## Path B: Debian Netinst + OMV

Use a minimal Debian install:
- `SSH server`
- `standard system utilities`
- no desktop
- no extra web server

After the first boot:
- copy or open `omv_on_debian_uefi_root.sh`
- run it as `root`
- example:

```bash
chmod +x omv_on_debian_uefi_root.sh
sudo ./omv_on_debian_uefi_root.sh eno1 192.168.15.1 --deploy-network
```

Replace:
- `eno1` with the real network interface
- `192.168.15.1` with your DNS server

## After OMV Is Running

1. Update packages.
2. Set static IP and hostname.
3. Create the HDD array.
4. Create filesystems and shares.
5. Enable `SMB`, `NFS`, `rsync` and `SSH`.
6. Install tape packages:

```bash
sudo apt-get update
sudo apt-get install --yes mt-st mtx bacula
```

If using `LTFS` on this host, also install the low-level SCSI helpers first:

```bash
sudo apt-get install --yes mt-st mtx sg3-utils lsscsi fuse3 attr
```

## Tape Bring-Up

Verify in this order:

```bash
lsscsi
ls -l /dev/st*
sudo mt -f /dev/st0 status
sudo mtx status
```

Only after that should you configure Bacula jobs and test a restore.

## Tape Validation Rule

Before trusting `LTFS`, validate raw tape I/O:

```bash
TAPE=/dev/nst0
dd if=/dev/urandom of=/root/tape-test.bin bs=1M count=10 iflag=fullblock
mt -f "$TAPE" rewind
mt -f "$TAPE" setblk 0 || true
dd if=/root/tape-test.bin of="$TAPE" bs=1M iflag=fullblock oflag=sync status=progress
mt -f "$TAPE" rewind
dd if="$TAPE" of=/root/tape-test-read.bin bs=1M count=10 iflag=fullblock status=progress
cmp -s /root/tape-test.bin /root/tape-test-read.bin
```

If this fails with messages such as:
- `LOOP DOWN`
- `blocked FC remote port time out`
- `Power-on or device reset occurred`
- `Error on write filemark`

then stop and troubleshoot the `FC` path before blaming `LTFS`.
