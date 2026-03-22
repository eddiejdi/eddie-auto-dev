# LTO-6 FC Troubleshooting Runbook

## Scope

This document records what was learned while bringing up the `HP LTO-6` tape path on the NAS host `192.168.15.4`.

Primary host:
- Hostname: `rpa4all-nas-001`
- OS: `Debian 13 + OMV 8`
- Tape drive: `HP Ultrium 6-SCSI`
- Drive serial: `HUL831AMRM`
- Drive revision: `J5SW`
- HBA: `QLogic QLE2462` dual-port `4 Gb`
- HBA firmware reported by kernel: `FW:v8.07.00`
- Linux driver reported by kernel: `DVR:v10.02.09.400-k`

Stable device links used in production:
- `/dev/tape/by-id/scsi-HUL831AMRM`
- `/dev/tape/by-id/scsi-HUL831AMRM-nst`
- `/dev/tape/by-id/scsi-HUL831AMRM-sg`

## Timeline Summary

Observed initial failure pattern:
- `LTFS` formatting and mounting could succeed.
- Real writes later failed.
- Kernel showed `qla2xxx ... LOOP DOWN`, `LOOP UP`, `blocked FC remote port time out`.
- Tape status degraded to invalid position state after failure.
- `LTFS` then reported media revalidation and missing `EOD` style errors.

Key diagnostic conclusion:
- The first decisive proof came from raw tape I/O.
- Direct writes to `/dev/tape/by-id/scsi-HUL831AMRM-nst` failed with `Input/output error` without `LTFS` mounted.
- This isolated the problem to the `FC/HBA/link/drive path`, not to `LTFS` alone.

Later correction:
- The tape path was corrected by adjusting `FC` retry/timeout behavior and rebooting.
- Post-fix validation passed:
  - raw write `10 MiB`
  - `write filemark`
  - raw readback
  - exact returned size `10,485,760` bytes

Current practical conclusion:
- The drive is operational.
- The main residual risk is physical FC quality, especially cable and `SFP` condition.
- Production `LTFS` writes are currently considered stable only in `single-path`.
- Dual-path must be treated as an explicit revalidation exercise, not as the default production mode.

## Known-Good Validation Procedure

1. Stop higher-level tape services first.

```bash
systemctl stop ltfs-lto6.service ltfs-cache-flush.timer ltfs-cache-flush.service 2>/dev/null || true
```

2. Confirm the drive and generic SCSI device exist.

```bash
lsscsi -g
ls -l /dev/st* /dev/nst* /dev/sg*
ls -l /dev/tape/by-id
```

3. Check basic tape status.

```bash
mt -f /dev/tape/by-id/scsi-HUL831AMRM status
```

Expected healthy baseline:
- tape online
- valid `LTO-6` density
- no repeated reset loop in kernel

4. Run raw write/read against the non-rewinding device.

```bash
TAPE=/dev/tape/by-id/scsi-HUL831AMRM-nst
TEST=/root/tape-raw-test.bin
READ=/root/tape-raw-readback.bin

dd if=/dev/urandom of="$TEST" bs=1M count=10 iflag=fullblock status=progress
sha256sum "$TEST"
mt -f "$TAPE" rewind
mt -f "$TAPE" setblk 0 || true
dd if="$TEST" of="$TAPE" bs=1M iflag=fullblock oflag=sync status=progress
mt -f "$TAPE" rewind
dd if="$TAPE" of="$READ" bs=1M count=10 iflag=fullblock status=progress
sha256sum "$TEST" "$READ"
cmp -s "$TEST" "$READ"
```

5. Inspect kernel immediately after the test.

```bash
journalctl -k --since '-10 min' | tail -n 200
```

6. Clean temporary files.

```bash
rm -f "$TEST" "$READ"
```

## Failure Signatures That Point to FC Path Issues

Treat these as transport-path symptoms first:
- `qla2xxx ... LOOP DOWN detected`
- `qla2xxx ... LOOP UP detected`
- `blocked FC remote port time out`
- `Power-on or device reset occurred`
- `Error on write filemark`

Why:
- These were observed during direct writes to `/dev/nst0`, before `LTFS` was involved.
- When they appear, the tape can later look logically damaged even if the original fault was transport.

## LTFS Lessons Learned

What was learned:
- `LTFS` can mount and still not be the root cause.
- A broken `LTFS` view after a write failure may be a secondary consequence of FC path loss.
- Do not keep retrying `ltfsck`, remounts, or reformats before testing raw tape I/O.
- Even when `mkltfs` and mount succeed, dual-path failover can still break real writes later with:
  - disrupted transport
  - reservation conflict
  - partial flush failure

Correct decision order:
1. stop `LTFS`
2. validate raw `/dev/nst0`
3. only return to `LTFS` if raw I/O passes
4. if production writes still fail, force `single-path` before blaming `LTFS` again

## QLogic / qla2xxx Notes

Observed module/host values during investigation:
- `ql2xtgt_tape_enable` existed and was tested
- toggling it did not solve the failing path by itself
- expanded `qla2xxx` logging was useful for confirming FC session loss

Useful runtime inspection:

```bash
modinfo qla2xxx | sed -n '1,160p'
grep . /sys/module/qla2xxx/parameters/* | sort
for h in /sys/class/fc_host/host*; do
  echo "== $(basename "$h") =="
  for f in symbolic_name port_state speed supported_speeds dev_loss_tmo port_name node_name; do
    [ -f "$h/$f" ] && printf '%s: ' "$f" && cat "$h/$f"
  done
done
```

Known observed values on this host:
- `symbolic_name: QLE2462 FW:v8.07.00 DVR:v10.02.09.400-k`
- one port can stay `Linkdown` while the active tape port is `Online`

## Remaining Physical Checks

Even with the corrected configuration, still inspect:
- FC cable condition
- `SFP` cleanliness
- connector seating
- HBA port stability
- drive-side transceiver or connector condition

Reason:
- `loss_of_signal` counters before the successful reboot indicated marginal physical link quality.
- FC links can pass short tests and still fail later under sustained streaming.

## Recommended Post-Fix Burn-In

Before resuming production migrations:
1. run raw `1 GiB` write/read
2. run raw `5 GiB` write/read
3. run `LTFS` mount
4. write small file through `LTFS`
5. run the first real spool flush in `single-path`
6. only after a stable burn-in window, consider re-testing dual-path

## Production Data Paths Used

Tape host local staging:
- `/var/spool/lto6-cache`

Historical source dataset:
- `/mnt/raid1/nextcloud-external/RPA4ALL`

Mountpoint used for `LTFS`:
- `/mnt/tape/lto6`

Compatibility symlink:
- `/srv/ltfs/lto6`

## External References

These sources matched the observed behavior and support matrix:
- Red Hat KB on tape backup failures and `WRITE_FILEMARK` with `QLogic HBA`: `https://access.redhat.com/solutions/387783`
- Marvell public driver downloads and release resources for `QLogic` FC adapters: `https://www.marvell.com/support/ldriver.html`
- HPE `StoreEver` / `Ultrium 6650 FC` documentation showing `J5SW` in supported material:
  - `https://support.hpe.com/hpesc/public/docDisplay?docId=a00128657zh_tw&docLocale=zh_TW`
  - `https://support.hpe.com/hpesc/public/docDisplay?docId=a00074512ko_kr&docLocale=ko_KR`

## Current Status

As of `2026-03-21`:
- `10 MiB` raw write/read passed
- `write filemark` passed
- exact readback size matched
- drive considered operational again
- physical FC inspection remains pending
