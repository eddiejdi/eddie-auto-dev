# NAS OMV + LTO Architecture

## Decision

Base platform: `openmediavault 8` on `Debian 13`.

Why this design:
- `8 GB RAM` is enough for OMV and file services without forcing a heavier storage stack.
- OMV gives a clean NAS web UI for `SMB`, `NFS`, `rsync`, `SSH`, disks and SMART.
- Debian underneath keeps the host flexible for `mt-st`, `mtx` and `Bacula` to drive the `LTO` unit.
- `ZFS` is intentionally not the default here because the same host will also handle tape jobs and only has `8 GB`.

## Install Media Strategy

Preferred installer:
- `openmediavault_8.0-12-amd64.iso`

Fallback installer:
- `debian-13.4.0-amd64-netinst.iso`

Reason for carrying both on Ventoy:
- The OMV ISO is the fastest path for a dedicated NAS install.
- The OMV docs state the official ISO path is `x86/AMD64 + BIOS`.
- If the target machine boots better in `UEFI`, install Debian first and then layer OMV on top.

## Physical Layout

Host:
- CPU: `Intel i5`
- RAM: `8 GB`
- System disk: `NVMe`
- Data disks: separate SATA HDDs
- Tape: `LTO drive` attached via the correct host interface, ideally a supported `SAS HBA`

Disk roles:
- `NVMe`: operating system only
- `HDD pool`: NAS data
- `LTO`: cold archive / offline backup target

## Storage Layout

Recommended disk design:
- If you have `2 HDDs`: use `RAID1`
- If you have `4 HDDs`: use `RAID10`
- Filesystem on top: `ext4` or `XFS`

Why:
- Lower RAM pressure than ZFS on this host size
- Easier recovery and wider tool compatibility
- Good fit for OMV plus tape workflows

Do not use:
- The system `NVMe` for shared folders
- Cheap USB disks as primary NAS storage
- The LTO tape as a mounted daily-access filesystem

## Network and Services

Core services to enable in OMV:
- `SMB` for desktops and mixed clients
- `NFS` for Linux hosts, containers and hypervisors
- `rsync` for controlled host-to-NAS pushes
- `SSH` for administration and tape operations

Recommended networking:
- Static IP for the NAS
- Reserve DNS entry in the homelab
- Optional VLAN separation for storage traffic if your switch supports it

## Tape Architecture

Tape control stack on the NAS host:
- `mt-st`
- `mtx` if you have a library/autoloader
- `Bacula` for scheduled backup catalog and tape jobs

Current field-proven host pattern:
- The tape drive is physically attached to the NAS host at `192.168.15.4`
- OS: `Debian 13 + OMV 8`
- Tape device family observed in production: `HP Ultrium 6-SCSI`
- FC path observed in production: `QLogic QLE2462` dual-port `4 Gb`
- Stable device links should be preferred over raw nodes:
  - `/dev/tape/by-id/scsi-HUL831AMRM`
  - `/dev/tape/by-id/scsi-HUL831AMRM-nst`
  - `/dev/tape/by-id/scsi-HUL831AMRM-sg`

Operational model:
- Disk is the primary online storage layer
- Tape is the cold archive / recovery layer
- Restore tests are mandatory after first setup

Suggested policy:
- Daily: host and share backups land on disk
- Weekly: full backup to `LTO`
- Optional mid-week: incremental tape jobs if retention requires it
- Monthly: verify at least one restore path from tape to disk

Operational warning:
- `LTFS` is acceptable for ad-hoc interchange and controlled archive workflows.
- Do not treat `LTFS` tape mountpoints as a normal low-latency shared filesystem.
- For sustained production backup, stage to disk first and write to tape in controlled jobs.

## Recommended Shares

Create separate shared folders instead of one giant share:
- `homes`
- `media`
- `backups`
- `vm-export`
- `tape-stage`

Purpose of `tape-stage`:
- Temporary landing zone for datasets that must be written to tape
- Keeps tape workflows isolated from user shares

Observed production staging model:
- `cloudnext` / Nextcloud data was staged first to local disk cache on the tape host
- Spool path used in production: `/var/spool/lto6-cache`
- This prevents remote clients from writing directly to a tape mount while link stability is still being validated

## Resource Budget

Initial rule set for an `8 GB` host:
- Keep the NAS host focused on storage and tape
- Do not start with Docker stacks on this machine
- Do not run VMs on this host
- Add monitoring only if lightweight

If you later expand to `16 GB+`, you can revisit:
- `Docker/Compose`
- `Btrfs snapshots`
- A separate backup catalog database

## Implementation Order

1. Install OMV using the OMV ISO if the machine boots it cleanly in BIOS/Legacy mode.
2. If OMV ISO is not suitable for the firmware path, install Debian 13 netinst and then install OMV using the root script included in this bundle.
3. Set static IP and hostname.
4. Update the system fully.
5. Create the HDD array and filesystem.
6. Create shared folders.
7. Enable SMB, NFS, rsync and SSH.
8. Install `mt-st`, `mtx` and `bacula`.
9. Validate the tape device with non-destructive commands first.
10. Run one full write and one test restore before production use.

## Tape Validation Sequence

After OMV is up and the tape is connected:
- Confirm the drive appears in `lsscsi` or `/dev/st*`
- Run `mt -f /dev/st0 status`
- If using a library, run `mtx status`
- Only then configure Bacula storage and jobs

Recommended FC validation order:
- Validate raw write/read to `/dev/nst0` before trusting `LTFS`
- If `LTFS` fails, test again with direct `dd` or `tar` to the non-rewinding tape device
- Treat `qla2xxx ... LOOP DOWN`, `blocked FC remote port time out`, `Power-on or device reset occurred`, and `Error on write filemark` as FC path failures first, not as `LTFS` proof by themselves
- Only return to `LTFS` after raw tape I/O passes repeatedly

Field lessons learned:
- Previous failures were traced to a combination of `FC` retry settings that were too aggressive for the link.
- The failure mode was an apparently broken `LTFS`, but raw tests later proved the transport path was the first unstable layer.
- After correcting the FC retry/timeout behavior and rebooting, the drive passed a `10 MiB` raw write/read validation including `write filemark`.
- A later production write window showed that dual-path `FC` was still unsafe on this host because failover caused `LTFS` transport disruption and drive reservation conflicts.
- The stable operating mode became `single-path FC` with disk-first staging and controlled flush to tape.
- Remaining operational risk is still physical FC hygiene:
  - cable wear
  - dirty or tired `SFP`
  - intermittent `loss_of_signal`

## Final Recommendation

Use this machine as:
- `Primary NAS`
- `Backup landing zone`
- `LTO writer`

Do not use this machine as:
- General virtualization host
- Heavy container host
- ZFS appliance

That split keeps the system aligned with the available RAM and with the LTO requirement.
