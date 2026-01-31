Restore procedure (partial / full) for rpa4all snapshots

Quick summary:
- Snapshots are full filesystem copies, now including /boot and /boot/efi (UEFI ESP).
- These are file-level snapshots created in /mnt/storage/backups/rpa4all-snapshot-<TS>.

Partial restore test (what we ran):
1. Create test image:
   sudo fallocate -l 130G /mnt/storage/restore-test-130G.img
   sudo losetup --find --show /mnt/storage/restore-test-130G.img  # gives /dev/loopX
   sudo mkfs.ext4 -F /dev/loopX
   sudo mkdir -p /mnt/restore-test && sudo mount /dev/loopX /mnt/restore-test
2. Restore snapshot into image:
   sudo rsync -aAXv --numeric-ids /mnt/storage/backups/rpa4all-snapshot-<TS>/ /mnt/restore-test/
3. Prepare chroot (bind pseudo-fs):
   sudo mkdir -p /mnt/restore-test/{dev,proc,sys,run,tmp,var/tmp}
   sudo mount --bind /dev /mnt/restore-test/dev
   sudo mount --bind /proc /mnt/restore-test/proc
   sudo mount --bind /sys /mnt/restore-test/sys
   sudo mount --bind /run /mnt/restore-test/run
4. Validate in chroot (no changes to host):
   sudo chroot /mnt/restore-test /bin/bash -lc "update-initramfs -u -k all || true; grub-mkconfig -o /boot/grub/grub.cfg"
   - This verifies that kernels/initramfs exist and grub configuration can be generated.
   - Reinstalling GRUB to a real disk requires care and a live environment (see next section).
5. Cleanup:
   sudo umount /mnt/restore-test/{run,sys,proc,dev}
   sudo umount /mnt/restore-test
   sudo losetup -d /dev/loopX

Full restore to disk (summary):
- Boot a rescue/live USB.
- Activate LVM if needed: vgchange -ay
- Mount target root and other partitions (boot, esp) under /mnt.
- rsync from snapshot into /mnt with same rsync options used in snapshot script.
- chroot into /mnt, reinstall kernel if /boot missing, and run grub-install (target disk) and update-grub.
- Reboot and verify.

Notes & caveats:
- Our snapshots are file-level; they are not 'drop-in' block images for GRUB. To be bootable you must restore /boot and ESP or reinstall GRUB after restoring.
- Keep an offsite copy (S3/rsync) for redundancy. Consider LVM-based block snapshots (faster/restorable) if you can free PV space or add a disk to the VG.

Contact: For assistance in automating restore tests or scheduling a periodic restore verification, open an issue or reply in the ticket.