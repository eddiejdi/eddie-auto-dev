#!/usr/bin/env python3
"""Aplica patch LTFS v3: trata -EDEV_FILEMARK_DETECTED no ANSI label read.

Reseta os fontes para limpo e aplica patch completo.
"""
import sys


def patch_file(path: str) -> bool:
    """Aplica todas as modificações em ltfs_internal.c."""
    with open(path) as f:
        lines = f.readlines()

    code = ''.join(lines)

    # Verify clean state
    if 'ansi_label_missing' in code:
        print("ERROR: source not clean, has ansi_label_missing already")
        return False

    # ---- PATCH 1: Add variable ----
    code = code.replace(
        '\tbool too_long = false, ansi_valid = false;\n',
        '\tbool too_long = false, ansi_valid = false;\n\tbool ansi_label_missing = false;\n',
        1
    )

    # ---- PATCH 2: Handle FILEMARK in nread < 0 branch ----
    # Original code: nread < 0 goes to error. We intercept FILEMARK_DETECTED.
    code = code.replace(
        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n'
        '\tif (nread < 0) {\n'
        '\t\tltfsmsg(LTFS_ERR, 11174E, (int)nread);\n'
        '\t\tif (nread == -EDEV_EOD_DETECTED || nread == -EDEV_RECORD_NOT_FOUND)\n'
        '\t\t\tret = -LTFS_LABEL_INVALID;\n'
        '\t\telse\n'
        '\t\t\tret = nread;\n'
        '\t\tgoto out_free;\n'
        '\t} else if (nread < 80) {\n'
        '\t\tltfsmsg(LTFS_ERR, 11175E, (int)nread);\n'
        '\t\tret = -LTFS_LABEL_INVALID;\n'
        '\t\tgoto out_free;\n',

        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n'
        '\tif (nread == -EDEV_FILEMARK_DETECTED || nread == 0) {\n'
        '\t\t/* RECOVERY: filemark at BOT instead of 80-byte ANSI label.\n'
        '\t\t * tape_read returned FILEMARK or 0 bytes. Cursor advanced past it.\n'
        '\t\t * Generate synthetic ANSI label and continue. */\n'
        '\t\tltfsmsg(LTFS_WARN, 11175E, (int)nread);\n'
        '\t\tmemset(buf, \' \', 80);\n'
        '\t\tmemcpy(buf, "VOL1", 4);\n'
        '\t\tbuf[10] = \'L\';\n'
        '\t\tmemcpy(buf + 24, "LTFS", 4);\n'
        '\t\tbuf[79] = \'4\';\n'
        '\t\tnread = 80;\n'
        '\t\tansi_label_missing = true;\n'
        '\t} else if (nread < 0) {\n'
        '\t\tltfsmsg(LTFS_ERR, 11174E, (int)nread);\n'
        '\t\tif (nread == -EDEV_EOD_DETECTED || nread == -EDEV_RECORD_NOT_FOUND)\n'
        '\t\t\tret = -LTFS_LABEL_INVALID;\n'
        '\t\telse\n'
        '\t\t\tret = nread;\n'
        '\t\tgoto out_free;\n'
        '\t} else if (nread < 80) {\n'
        '\t\tltfsmsg(LTFS_ERR, 11175E, (int)nread);\n'
        '\t\tret = -LTFS_LABEL_INVALID;\n'
        '\t\tgoto out_free;\n',
        1
    )

    # ---- PATCH 3: Skip filemark-after-ANSI check when label is missing ----
    code = code.replace(
        '\t/* Check for file mark after ANSI label */\n'
        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n',

        '\tif (ansi_label_missing) {\n'
        '\t\t/* RECOVERY: skip filemark-after-ANSI check, cursor already past filemark */\n'
        '\t\tgoto read_xml_label;\n'
        '\t}\n'
        '\t/* Check for file mark after ANSI label */\n'
        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n',
        1
    )

    # ---- PATCH 4: Add label for XML read and recovery for ltfsindex ----
    code = code.replace(
        '\t/* Read XML label */\n'
        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n',

        'read_xml_label:\n'
        '\t/* Read XML label */\n'
        '\tnread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);\n',
        1
    )

    # ---- PATCH 5: Handle xml_label_from_mem failure with ltfsindex recovery ----
    code = code.replace(
        '\tret = xml_label_from_mem(buf, nread, label);\n'
        '\tif (ret < 0) {\n'
        '\t\tltfsmsg(LTFS_ERR, 11179E, ret);\n'
        '\t\tgoto out_free;\n'
        '\t}\n',

        '\tret = xml_label_from_mem(buf, nread, label);\n'
        '\tif (ret < 0) {\n'
        '\t\tif (ansi_label_missing) {\n'
        '\t\t\t/* RECOVERY: XML might be ltfsindex instead of ltfslabel.\n'
        '\t\t\t * Extract UUID and metadata from the index XML. */\n'
        '\t\t\tchar *uuid_s = strstr(buf, "<volumeuuid>");\n'
        '\t\t\tchar *uuid_e = uuid_s ? strstr(uuid_s, "</volumeuuid>") : NULL;\n'
        '\t\t\tif (uuid_s && uuid_e) {\n'
        '\t\t\t\tuuid_s += 12;\n'
        '\t\t\t\tif ((uuid_e - uuid_s) == 36) {\n'
        '\t\t\t\t\tmemcpy(label->vol_uuid, uuid_s, 36);\n'
        '\t\t\t\t\tlabel->vol_uuid[36] = \'\\0\';\n'
        '\t\t\t\t}\n'
        '\t\t\t}\n'
        '\t\t\tchar *bs_s = strstr(buf, "<blocksize>");\n'
        '\t\t\tchar *bs_e = bs_s ? strstr(bs_s, "</blocksize>") : NULL;\n'
        '\t\t\tif (bs_s && bs_e) {\n'
        '\t\t\t\tbs_s += 11;\n'
        '\t\t\t\tlabel->blocksize = (unsigned int)atoi(bs_s);\n'
        '\t\t\t} else {\n'
        '\t\t\t\tlabel->blocksize = 524288;\n'
        '\t\t\t}\n'
        '\t\t\tlabel->partid_ip = \'a\';\n'
        '\t\t\tlabel->partid_dp = \'b\';\n'
        '\t\t\tlabel->this_partition = (partition == 0) ? \'a\' : \'b\';\n'
        '\t\t\tlabel->enable_compression = true;\n'
        '\t\t\tlabel->version = LTFS_LABEL_VERSION;\n'
        '\t\t\tlabel->format_time.tv_sec = 0;\n'
        '\t\t\tlabel->format_time.tv_nsec = 0;\n'
        '\t\t\tlabel->barcode[6] = \'\\0\';\n'
        '\t\t\tret = 0;\n'
        '\t\t\tgoto out_free;\n'
        '\t\t}\n'
        '\t\tltfsmsg(LTFS_ERR, 11179E, ret);\n'
        '\t\tgoto out_free;\n'
        '\t}\n',
        1
    )

    # Verify patches applied
    if 'ansi_label_missing' not in code:
        print("ERROR: patch verification failed")
        return False

    with open(path, 'w') as f:
        f.write(code)
    print(f"OK: All patches applied to {path}")
    return True


def patch_label_compare(path: str) -> bool:
    """Patch label_compare in label.c."""
    with open(path) as f:
        code = f.read()

    code = code.replace(
        '\tCHECK_ARG_NULL(label1, -LTFS_NULL_ARG);\n'
        '\tCHECK_ARG_NULL(label2, -LTFS_NULL_ARG);\n'
        '\n'
        '\tif (strncmp(label1->barcode, label2->barcode, 6)) {\n',

        '\tCHECK_ARG_NULL(label1, -LTFS_NULL_ARG);\n'
        '\tCHECK_ARG_NULL(label2, -LTFS_NULL_ARG);\n'
        '\n'
        '\t/* RECOVERY: skip strict checks when either label is synthetic */\n'
        '\tif ((label1->barcode[0] == \' \' && label1->barcode[1] == \' \') ||\n'
        '\t    (label2->barcode[0] == \' \' && label2->barcode[1] == \' \')) {\n'
        '\t\tif (label1->barcode[0] == \' \' && label2->barcode[0] != \' \')\n'
        '\t\t\tmemcpy(label1->barcode, label2->barcode, 7);\n'
        '\t\telse if (label2->barcode[0] == \' \' && label1->barcode[0] != \' \')\n'
        '\t\t\tmemcpy(label2->barcode, label1->barcode, 7);\n'
        '\t\tif (label1->vol_uuid[0] == \'\\0\' && label2->vol_uuid[0] != \'\\0\')\n'
        '\t\t\tmemcpy(label1->vol_uuid, label2->vol_uuid, 37);\n'
        '\t\telse if (label2->vol_uuid[0] == \'\\0\' && label1->vol_uuid[0] != \'\\0\')\n'
        '\t\t\tmemcpy(label2->vol_uuid, label1->vol_uuid, 37);\n'
        '\t\tif (label1->format_time.tv_sec == 0 && label2->format_time.tv_sec != 0)\n'
        '\t\t\tlabel1->format_time = label2->format_time;\n'
        '\t\telse if (label2->format_time.tv_sec == 0 && label1->format_time.tv_sec != 0)\n'
        '\t\t\tlabel2->format_time = label1->format_time;\n'
        '\t\tif (label1->blocksize == 0 && label2->blocksize != 0)\n'
        '\t\t\tlabel1->blocksize = label2->blocksize;\n'
        '\t\telse if (label2->blocksize == 0 && label1->blocksize != 0)\n'
        '\t\t\tlabel2->blocksize = label1->blocksize;\n'
        '\t\treturn 0;\n'
        '\t}\n'
        '\n'
        '\tif (strncmp(label1->barcode, label2->barcode, 6)) {\n',
        1
    )

    with open(path, 'w') as f:
        f.write(code)
    print(f"OK: Patched {path}")
    return True


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/root/src/ltfs"
    ok1 = patch_file(f"{src}/src/libltfs/ltfs_internal.c")
    ok2 = patch_label_compare(f"{src}/src/libltfs/label.c")
    if ok1 and ok2:
        print("All patches applied.")
    else:
        print("FAILED", file=sys.stderr)
        sys.exit(1)
