# LTO Multi-Drive Unified Mount

## Goal

Expose a single logical mount to clients while distributing archived files across
multiple LTFS tape branches.

This does **not** stripe or resize LTFS across cartridges. Each file is stored
whole on exactly one tape branch, and the logical single mount is created above
those branches.

## Why this design

Official LTFS behavior is per cartridge and per mounted LTFS filesystem.
IBM Storage Archive can manage libraries and multiple drives, but the underlying
media still remain separate volumes. For a homelab deployment the pragmatic
approach is:

- one logical client mount
- local disk cache as the write landing zone
- one LTFS mount per drive
- a worker that routes completed files to a healthy LTFS branch
- a union filesystem that presents cache plus LTFS branches as one namespace

## Topology

Client-facing logical namespace:

- `/mnt/lto-archive`

Local write buffer:

- `/mnt/raid1/lto6-cache`

Current LTFS tape branches:

- `/mnt/lto6`
- `/mnt/lto6b`

Legacy remote cache kept for drain:

- `/mnt/lto6-cache-nas`

## Runtime flow

1. Clients write to `/mnt/lto-archive`.
2. `mergerfs` prefers the cache branch first, so new files land on local disk.
3. `ltfs-cache-flush` scans stable files in the cache.
4. The worker chooses one healthy LTFS branch based on placement policy.
5. The source is removed from cache after size verification.
6. The file remains visible through `/mnt/lto-archive` because the union mount
   also includes the LTFS branches.

## Important behavior

- New files are placed on the target with the most free space by default.
- Once a logical path is archived, placement is remembered so updates keep using
  the same LTFS branch.
- If no LTFS branch is healthy, the cache keeps accumulating data.
- If only one LTFS branch is healthy, the logical mount still works.
- Archived files are visible through the logical mount only while their
  corresponding LTFS branch is mounted and present in the union.

## Deployed components

Worker and placement catalog:

- `/usr/local/bin/ltfs-cache-flush`
- `/var/lib/ltfs-cache-flush/state.json`
- `/var/lib/ltfs-cache-flush/placements.json`
- `/var/lib/ltfs-cache-flush/catalog.jsonl`

Logical mount refresher:

- `/usr/local/bin/lto-logical-mount`
- `/etc/default/lto-logical-mount`
- `lto-logical-mount-refresh.service`
- `lto-logical-mount-refresh.timer`

## Add a second drive

1. Expose a second LTFS share and mount it on the homelab, for example
   `/mnt/lto6b`.
2. Append that path to both:
   - `TARGET_ROOTS` in `/etc/default/ltfs-cache-flush`
   - `TAPE_BRANCHES` in `/etc/default/lto-logical-mount`
3. Run:

```bash
sudo systemctl start lto-logical-mount-refresh.service
sudo systemctl start ltfs-cache-flush.service
```

4. Validate:

```bash
findmnt /mnt/lto-archive
stat -f /mnt/lto6
stat -f /mnt/lto6b
journalctl -u ltfs-cache-flush.service -n 50 --no-pager
```

## Constraints

- This is a logical single mount, not a block-level aggregate filesystem.
- LTFS media cannot be "resized" together like disk filesystems.
- There is no redundancy or striping across tapes.
- If you need transparent recall across many unloaded tapes, use a cataloged
  tape stack such as IBM Storage Archive library workflows or Bacula, not raw
  LTFS mounts alone.

## References

- IBM Storage Archive overview: https://www.ibm.com/products/storage-archive
- IBM LTFS format whitepaper: https://delivery04.dhe.ibm.com/sar/CMA/STA/040bt/2/LFV_Whitepaper.pdf
- mergerfs documentation: https://github.com/trapexit/mergerfs
