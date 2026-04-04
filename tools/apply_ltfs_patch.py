#!/usr/bin/env python3
"""Applies recovery patches to LTFS source on the NAS.

Modifies ltfs_internal.c:ltfs_read_one_label to handle missing ANSI labels,
and label.c:label_compare to handle synthetic labels.
"""
import sys

def patch_ltfs_internal(path):
    """Patch ltfs_read_one_label in ltfs_internal.c."""
    with open(path, 'r') as f:
        code = f.read()

    # 1. Add ansi_label_missing variable declaration
    old = '\tbool too_long = false, ansi_valid = false;'
    new = '\tbool too_long = false, ansi_valid = false;\n\tbool ansi_label_missing = false;'
    if old not in code:
        print(f"ERROR: could not find declaration line")
        return False
    code = code.replace(old, new, 1)

    # 2. Replace the nread < 80 error block with recovery logic
    old_block = '''\t} else if (nread < 80) {
\t\tltfsmsg(LTFS_ERR, 11175E, (int)nread);
\t\tret = -LTFS_LABEL_INVALID;
\t\tgoto out_free;
\t} else if (nread > 80) {'''

    new_block = '''\t} else if (nread < 80) {
\t\tif (nread == 0) {
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
\t\t}
\t} else if (nread > 80) {'''

    if old_block not in code:
        print("ERROR: could not find nread < 80 block")
        return False
    code = code.replace(old_block, new_block, 1)

    # 3. Wrap the filemark-after-ANSI check in if (!ansi_label_missing)
    old_fm = '''\t/* Check for file mark after ANSI label */
\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
\tif (nread < 0) {
\t\tltfsmsg(LTFS_ERR, 11295E, (int)nread);
\t\tif (nread == -EDEV_EOD_DETECTED)
\t\t\tret = -LTFS_LABEL_INVALID;
\t\telse
\t\t\tret = nread;
\t\tgoto out_free;
\t} else if (nread > 0) {
\t\t/* no file mark after ANSI label */
\t\tltfsmsg(LTFS_ERR, 11296E);
\t\tret = -LTFS_LABEL_INVALID;
\t\tgoto out_free;
\t}'''

    new_fm = '''\tif (!ansi_label_missing) {
\t\t/* Check for file mark after ANSI label */
\t\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
\t\tif (nread < 0) {
\t\t\tltfsmsg(LTFS_ERR, 11295E, (int)nread);
\t\t\tif (nread == -EDEV_EOD_DETECTED)
\t\t\t\tret = -LTFS_LABEL_INVALID;
\t\t\telse
\t\t\t\tret = nread;
\t\t\tgoto out_free;
\t\t} else if (nread > 0) {
\t\t\t/* no file mark after ANSI label */
\t\t\tltfsmsg(LTFS_ERR, 11296E);
\t\t\tret = -LTFS_LABEL_INVALID;
\t\t\tgoto out_free;
\t\t}
\t}'''

    if old_fm not in code:
        print("ERROR: could not find filemark-after-ANSI block")
        return False
    code = code.replace(old_fm, new_fm, 1)

    # 4. After xml_label_from_mem fails, add recovery for ltfsindex-as-label
    old_xml_fail = '''\tret = xml_label_from_mem(buf, nread, label);
\tif (ret < 0) {
\t\tltfsmsg(LTFS_ERR, 11179E, ret);
\t\tgoto out_free;
\t}'''

    new_xml_fail = '''\tret = xml_label_from_mem(buf, nread, label);
\tif (ret < 0) {
\t\tif (ansi_label_missing) {
\t\t\t/* RECOVERY: XML is ltfsindex, not ltfslabel. Synthesize label from index. */
\t\t\tchar *uuid_s = strstr(buf, "<volumeuuid>");
\t\t\tchar *uuid_e = uuid_s ? strstr(uuid_s, "</volumeuuid>") : NULL;
\t\t\tif (uuid_s && uuid_e) {
\t\t\t\tuuid_s += 12;
\t\t\t\tif ((uuid_e - uuid_s) == 36) {
\t\t\t\t\tmemcpy(label->vol_uuid, uuid_s, 36);
\t\t\t\t\tlabel->vol_uuid[36] = '\\0';
\t\t\t\t}
\t\t\t}
\t\t\tchar *bs_s = strstr(buf, "<blocksize>");
\t\t\tchar *bs_e = bs_s ? strstr(bs_s, "</blocksize>") : NULL;
\t\t\tif (bs_s && bs_e) {
\t\t\t\tbs_s += 11;
\t\t\t\tlabel->blocksize = (unsigned int)atoi(bs_s);
\t\t\t} else {
\t\t\t\tlabel->blocksize = 524288;
\t\t\t}
\t\t\tlabel->partid_ip = 'a';
\t\t\tlabel->partid_dp = 'b';
\t\t\tlabel->this_partition = (partition == 0) ? 'a' : 'b';
\t\t\tlabel->enable_compression = true;
\t\t\tlabel->version = LTFS_LABEL_VERSION;
\t\t\tlabel->format_time.tv_sec = 0;
\t\t\tlabel->format_time.tv_nsec = 0;
\t\t\tlabel->barcode[6] = '\\0';
\t\t\tret = 0;
\t\t\tgoto out_free;
\t\t}
\t\tltfsmsg(LTFS_ERR, 11179E, ret);
\t\tgoto out_free;
\t}'''

    if old_xml_fail not in code:
        print("ERROR: could not find xml_label_from_mem block")
        return False
    code = code.replace(old_xml_fail, new_xml_fail, 1)

    with open(path, 'w') as f:
        f.write(code)
    print(f"OK: Patched {path}")
    return True


def patch_label_compare(path):
    """Patch label_compare in label.c to handle synthetic labels."""
    with open(path, 'r') as f:
        code = f.read()

    old = '''\tCHECK_ARG_NULL(label1, -LTFS_NULL_ARG);
\tCHECK_ARG_NULL(label2, -LTFS_NULL_ARG);

\tif (strncmp(label1->barcode, label2->barcode, 6)) {'''

    new = '''\tCHECK_ARG_NULL(label1, -LTFS_NULL_ARG);
\tCHECK_ARG_NULL(label2, -LTFS_NULL_ARG);

\t/* RECOVERY: skip strict checks if either label is synthetic (spaces barcode) */
\tif ((label1->barcode[0] == ' ' && label1->barcode[1] == ' ') ||
\t    (label2->barcode[0] == ' ' && label2->barcode[1] == ' ')) {
\t\t/* Copy valid barcode to synthetic label */
\t\tif (label1->barcode[0] == ' ' && label2->barcode[0] != ' ')
\t\t\tmemcpy(label1->barcode, label2->barcode, 7);
\t\telse if (label2->barcode[0] == ' ' && label1->barcode[0] != ' ')
\t\t\tmemcpy(label2->barcode, label1->barcode, 7);
\t\t/* Copy UUID if missing */
\t\tif (label1->vol_uuid[0] == '\\0' && label2->vol_uuid[0] != '\\0')
\t\t\tmemcpy(label1->vol_uuid, label2->vol_uuid, 37);
\t\telse if (label2->vol_uuid[0] == '\\0' && label1->vol_uuid[0] != '\\0')
\t\t\tmemcpy(label2->vol_uuid, label1->vol_uuid, 37);
\t\t/* Copy format_time if zero */
\t\tif (label1->format_time.tv_sec == 0 && label2->format_time.tv_sec != 0)
\t\t\tlabel1->format_time = label2->format_time;
\t\telse if (label2->format_time.tv_sec == 0 && label1->format_time.tv_sec != 0)
\t\t\tlabel2->format_time = label1->format_time;
\t\t/* Copy blocksize if zero */
\t\tif (label1->blocksize == 0 && label2->blocksize != 0)
\t\t\tlabel1->blocksize = label2->blocksize;
\t\telse if (label2->blocksize == 0 && label1->blocksize != 0)
\t\t\tlabel2->blocksize = label1->blocksize;
\t\treturn 0;
\t}

\tif (strncmp(label1->barcode, label2->barcode, 6)) {'''

    if old not in code:
        print("ERROR: could not find label_compare block")
        return False
    code = code.replace(old, new, 1)

    with open(path, 'w') as f:
        f.write(code)
    print(f"OK: Patched {path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: apply_ltfs_patch.py <ltfs_src_dir>")
        sys.exit(1)

    src_dir = sys.argv[1]
    ok1 = patch_ltfs_internal(f"{src_dir}/src/libltfs/ltfs_internal.c")
    ok2 = patch_label_compare(f"{src_dir}/src/libltfs/label.c")

    if ok1 and ok2:
        print("\nAll patches applied successfully.")
        sys.exit(0)
    else:
        print("\nSome patches FAILED.")
        sys.exit(1)
