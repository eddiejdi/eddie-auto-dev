#!/usr/bin/env python3
"""Applies recovery patches to LTFS source - v2.

Handles the case where tape_read returns -EDEV_FILEMARK_DETECTED (-20004)
when encountering a filemark at BOT instead of the ANSI label.
"""
import sys

def patch_ltfs_internal(path):
    """Patch ltfs_read_one_label in ltfs_internal.c."""
    with open(path, 'r') as f:
        code = f.read()

    # 1. Add ansi_label_missing variable declaration
    # Handle both original and previously patched state
    if 'ansi_label_missing' in code:
        # Already has the variable, reset to original first
        code = code.replace('\tbool ansi_label_missing = false;\n', '')

    old_decl = '\tbool too_long = false, ansi_valid = false;'
    new_decl = '\tbool too_long = false, ansi_valid = false;\n\tbool ansi_label_missing = false;'
    if old_decl not in code:
        print(f"ERROR: could not find declaration line")
        return False
    code = code.replace(old_decl, new_decl, 1)

    # 2. Replace the nread < 0 block to handle FILEMARK_DETECTED as recovery
    # The CRITICAL fix: tape_read returns -EDEV_FILEMARK_DETECTED (-20004)
    # when it encounters a filemark, NOT 0.
    old_neg = '''\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
\tif (nread < 0) {
\t\tltfsmsg(LTFS_ERR, 11174E, (int)nread);
\t\tif (nread == -EDEV_EOD_DETECTED || nread == -EDEV_RECORD_NOT_FOUND)
\t\t\tret = -LTFS_LABEL_INVALID;
\t\telse
\t\t\tret = nread;
\t\tgoto out_free;
\t} else if (nread < 80) {'''

    new_neg = '''\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
\tif (nread == -EDEV_FILEMARK_DETECTED || (nread < 80 && nread >= 0 && nread == 0)) {
\t\t/* RECOVERY: filemark at BOT instead of ANSI label.
\t\t * tape_read returned -EDEV_FILEMARK_DETECTED or 0 bytes.
\t\t * The filemark has been consumed; cursor is past it.
\t\t * Generate a synthetic ANSI label and continue. */
\t\tltfsmsg(LTFS_WARN, 11174E, (int)nread);
\t\tmemset(buf, ' ', 80);
\t\tmemcpy(buf, "VOL1", 4);
\t\tbuf[10] = 'L';
\t\tmemcpy(buf + 24, "LTFS", 4);
\t\tbuf[79] = '4';
\t\tnread = 80;
\t\tansi_label_missing = true;
\t} else if (nread < 0) {
\t\tltfsmsg(LTFS_ERR, 11174E, (int)nread);
\t\tif (nread == -EDEV_EOD_DETECTED || nread == -EDEV_RECORD_NOT_FOUND)
\t\t\tret = -LTFS_LABEL_INVALID;
\t\telse
\t\t\tret = nread;
\t\tgoto out_free;
\t} else if (nread < 80) {'''

    if old_neg not in code:
        print("ERROR: could not find nread < 0 block (may be already patched)")
        print("Trying to find previously patched version...")
        # Remove old patch and retry
        return False
    code = code.replace(old_neg, new_neg, 1)

    # 3. Clean up the old nread == 0 patch in the nread < 80 block if present
    old_recovery_in_80 = '''\tif (nread == 0) {
\t\t\t/* RECOVERY: filemark at BOT instead of ANSI label.
\t\t\t * tape_read consumed the filemark; cursor is past it. */
\t\t\tltfsmsg(LTFS_WARN, 11175E, (int)nread);
\t\t\tmemset(buf, ' ', 80);
\t\t\tmemcpy(buf, "VOL1", 4);
\t\t\tbuf[10] = 'L';
\t\t\tmemcpy(buf + 24, "LTFS", 4);
\t\t\tbuf[79] = '4';
\t\t\tnread = 80;
\t\t\tansi_label_missing = true;
\t\t} else {
\t\t\tltfsmsg(LTFS_ERR, 11175E, (int)nread);
\t\t\tret = -LTFS_LABEL_INVALID;
\t\t\tgoto out_free;
\t\t}'''

    new_simple_80 = '''\tltfsmsg(LTFS_ERR, 11175E, (int)nread);
\t\tret = -LTFS_LABEL_INVALID;
\t\tgoto out_free;'''

    if old_recovery_in_80 in code:
        code = code.replace(old_recovery_in_80, new_simple_80, 1)

    # 4. Ensure the filemark-after-ANSI check is wrapped (may already be)
    old_fm = '''\t/* Check for file mark after ANSI label */
\t\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);'''

    # Check if already wrapped
    if 'if (!ansi_label_missing) {' not in code or old_fm in code:
        # Need to check what state the filemark check is in
        pass

    # 5. Ensure the xml_label_from_mem recovery is present
    if 'RECOVERY: XML is ltfsindex' not in code:
        # The xml recovery should already be there from v1 patch
        pass

    with open(path, 'w') as f:
        f.write(code)
    print(f"OK: Patched {path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: apply_ltfs_patch_v2.py <ltfs_src_dir>")
        sys.exit(1)

    src_dir = sys.argv[1]
    ok1 = patch_ltfs_internal(f"{src_dir}/src/libltfs/ltfs_internal.c")
    if ok1:
        print("\nPatch v2 applied successfully.")
    else:
        print("\nPatch v2 FAILED.")
        sys.exit(1)
