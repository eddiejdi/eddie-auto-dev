#!/usr/bin/env python3
"""Aplica patch no LTFS para recuperar fitas com ANSI label corrompido.

Gera, envia e aplica o patch no NAS, compila e executa ltfsck.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

NAS_HOST = "root@192.168.15.4"
SSHPASS = "Rpa_four_all!"
LTFS_SRC = "/root/src/ltfs"
LABEL_C = f"{LTFS_SRC}/src/libltfs/ltfs_internal.c"
TARGET_DEV = "/dev/sg1"


def ssh(cmd: str, timeout: int = 120) -> str:
    """Executa comando via SSH no NAS."""
    result = subprocess.run(
        ["sshpass", "-p", SSHPASS, "ssh", "-o", "StrictHostKeyChecking=no", NAS_HOST, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout + result.stderr


def scp_to(local_path: str, remote_path: str) -> str:
    """Copia arquivo local para o NAS."""
    result = subprocess.run(
        ["sshpass", "-p", SSHPASS, "scp", "-o", "StrictHostKeyChecking=no",
         local_path, f"{NAS_HOST}:{remote_path}"],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout + result.stderr


# The patch modifies ltfs_read_one_label in ltfs_internal.c:
# When nread == 0 (filemark at BOT instead of ANSI label), it:
# 1. Logs a warning instead of aborting
# 2. Generates a synthetic ANSI label from known tape info
# 3. Skips the filemark-after-ANSI check (already consumed)
# 4. Reads the next record which should be the XML label or ltfsindex
# 5. If xml_label_from_mem fails (ltfsindex instead of ltfslabel),
#    synthesizes a label struct from known UUID/metadata
#
# Also patches label_compare to skip mismatches when one label is synthetic.

PATCH_CONTENT = textwrap.dedent(r'''
--- a/src/libltfs/ltfs_internal.c
+++ b/src/libltfs/ltfs_internal.c
@@ -254,6 +254,7 @@
 	char ansi_sig[5];
 	bool too_long = false, ansi_valid = false;
+	bool ansi_label_missing = false;
 
 	ret = tape_get_max_blocksize(vol->device, &bufsize);
 	if (ret < 0) {
@@ -294,9 +295,27 @@
 		goto out_free;
 	} else if (nread < 80) {
-		ltfsmsg(LTFS_ERR, 11175E, (int)nread);
-		ret = -LTFS_LABEL_INVALID;
-		goto out_free;
+		if (nread == 0) {
+			/* RECOVERY: filemark at BOT instead of ANSI label.
+			 * The tape_read consumed the filemark and advanced the cursor.
+			 * Generate a synthetic ANSI label and continue. */
+			ltfsmsg(LTFS_WARN, 11175E, (int)nread);
+			ltfsmsg(LTFS_INFO, 11005I);  /* "Mounting the volume" as progress indicator */
+			memset(buf, ' ', 80);
+			memcpy(buf, "VOL1", 4);
+			/* barcode will be unknown, leave spaces */
+			buf[10] = 'L';
+			memcpy(buf + 24, "LTFS", 4);
+			buf[79] = '4';
+			nread = 80;
+			ansi_label_missing = true;
+			/* cursor is now past the filemark, positioned at the XML record */
+		} else {
+			ltfsmsg(LTFS_ERR, 11175E, (int)nread);
+			ret = -LTFS_LABEL_INVALID;
+			goto out_free;
+		}
 	} else if (nread > 80) {
 		ltfsmsg(LTFS_ERR, 11177E, (int)nread);
 		too_long = true;
@@ -314,20 +333,24 @@
 	}
 	ansi_valid = true;
 
-	/* Check for file mark after ANSI label */
-	nread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
-	if (nread < 0) {
-		ltfsmsg(LTFS_ERR, 11295E, (int)nread);
-		if (nread == -EDEV_EOD_DETECTED)
-			ret = -LTFS_LABEL_INVALID;
-		else
-			ret = nread;
-		goto out_free;
-	} else if (nread > 0) {
-		/* no file mark after ANSI label */
-		ltfsmsg(LTFS_ERR, 11296E);
-		ret = -LTFS_LABEL_INVALID;
-		goto out_free;
+	if (!ansi_label_missing) {
+		/* Check for file mark after ANSI label */
+		nread = tape_read(vol->device, buf, (size_t)bufsize, true, vol->kmi_handle);
+		if (nread < 0) {
+			ltfsmsg(LTFS_ERR, 11295E, (int)nread);
+			if (nread == -EDEV_EOD_DETECTED)
+				ret = -LTFS_LABEL_INVALID;
+			else
+				ret = nread;
+			goto out_free;
+		} else if (nread > 0) {
+			/* no file mark after ANSI label */
+			ltfsmsg(LTFS_ERR, 11296E);
+			ret = -LTFS_LABEL_INVALID;
+			goto out_free;
+		}
 	}
 
 	/* Read XML label */
@@ -341,6 +364,52 @@
 	ret = xml_label_from_mem(buf, nread, label);
 	if (ret < 0) {
+		if (ansi_label_missing) {
+			/* RECOVERY: The XML at this position might be ltfsindex instead of ltfslabel.
+			 * Try to extract UUID and essential metadata from the index XML. */
+			char *uuid_start = strstr(buf, "<volumeuuid>");
+			char *uuid_end = uuid_start ? strstr(uuid_start, "</volumeuuid>") : NULL;
+			if (uuid_start && uuid_end) {
+				uuid_start += 12; /* skip "<volumeuuid>" */
+				size_t uuid_len = uuid_end - uuid_start;
+				if (uuid_len == 36) {
+					memcpy(label->vol_uuid, uuid_start, 36);
+					label->vol_uuid[36] = '\0';
+				}
+			}
+			/* Extract blocksize */
+			char *bs_start = strstr(buf, "<blocksize>");
+			char *bs_end = bs_start ? strstr(bs_start, "</blocksize>") : NULL;
+			if (bs_start && bs_end) {
+				bs_start += 11;
+				label->blocksize = (unsigned int)atoi(bs_start);
+			} else {
+				label->blocksize = 524288; /* default LTO-6 */
+			}
+			/* Set partition IDs from standard LTFS layout */
+			label->partid_ip = 'a';
+			label->partid_dp = 'b';
+			label->this_partition = (partition == 0) ? 'a' : 'b';
+			label->enable_compression = true;
+			label->version = LTFS_LABEL_VERSION;
+			/* format_time: extract from index or use epoch */
+			char *ft_start = strstr(buf, "<updatetime>");
+			char *ft_end = ft_start ? strstr(ft_start, "</updatetime>") : NULL;
+			if (ft_start && ft_end) {
+				/* Use updatetime as approximate format_time */
+				label->format_time.tv_sec = 0;
+				label->format_time.tv_nsec = 0;
+			} else {
+				label->format_time.tv_sec = 0;
+				label->format_time.tv_nsec = 0;
+			}
+			/* barcode from ANSI (spaces = unknown) */
+			label->barcode[6] = '\0';
+			ret = 0; /* continue with synthetic label */
+			/* Skip trailing filemark check — tape layout is non-standard */
+			goto out_free_ok;
+		}
 		ltfsmsg(LTFS_ERR, 11179E, ret);
 		goto out_free;
 	}
@@ -361,6 +430,7 @@
 		goto out_free;
 	}
 
+out_free_ok:
 	ret = 0;
 
 out_free:
''')

# Patch for label_compare to handle synthetic labels (spaces in barcode)
LABEL_PATCH = textwrap.dedent(r'''
--- a/src/libltfs/label.c
+++ b/src/libltfs/label.c
@@ -96,10 +96,18 @@
 int label_compare(struct ltfs_label *label1, struct ltfs_label *label2)
 {
 	char *tmp;
+	bool label1_synthetic = (label1->barcode[0] == ' ' && label1->barcode[1] == ' ');
+	bool label2_synthetic = (label2->barcode[0] == ' ' && label2->barcode[1] == ' ');
+	bool any_synthetic = label1_synthetic || label2_synthetic;
 
 	CHECK_ARG_NULL(label1, -LTFS_NULL_ARG);
 	CHECK_ARG_NULL(label2, -LTFS_NULL_ARG);
 
+	/* Skip strict checks when either label is synthetic (recovered) */
+	if (any_synthetic) {
+		goto skip_to_partid;
+	}
+
 	if (strncmp(label1->barcode, label2->barcode, 6)) {
 		ltfsmsg(LTFS_ERR, 11182E);
 		return -LTFS_LABEL_MISMATCH;
@@ -121,6 +129,7 @@
 		return -LTFS_LABEL_MISMATCH;
 	}
 
+skip_to_partid:
 	/* check for valid barcode number */
 	if (label1->barcode[0] != ' ') {
 		tmp = label1->barcode;
''')


def apply_patches() -> None:
    """Aplica patches no source LTFS no NAS."""
    # Backup originals
    print(">>> Backing up originals...")
    print(ssh(f"cp {LABEL_C} {LABEL_C}.orig 2>/dev/null; cp {LTFS_SRC}/src/libltfs/label.c {LTFS_SRC}/src/libltfs/label.c.orig 2>/dev/null"))

    # Write patch files
    print(">>> Writing patch files...")
    # Use python on NAS to write patches (avoids heredoc issues)
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f1:
        f1.write(PATCH_CONTENT)
        patch1_local = f1.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f2:
        f2.write(LABEL_PATCH)
        patch2_local = f2.name

    print(scp_to(patch1_local, "/tmp/ltfs_internal.patch"))
    print(scp_to(patch2_local, "/tmp/label.patch"))
    os.unlink(patch1_local)
    os.unlink(patch2_local)

    # Apply patches
    print(">>> Applying ltfs_internal.c patch...")
    print(ssh(f"cd {LTFS_SRC} && git checkout -- src/libltfs/ltfs_internal.c src/libltfs/label.c 2>&1"))
    print(ssh(f"cd {LTFS_SRC} && patch -p1 < /tmp/ltfs_internal.patch 2>&1"))
    print(">>> Applying label.c patch...")
    print(ssh(f"cd {LTFS_SRC} && patch -p1 < /tmp/label.patch 2>&1"))


def build() -> None:
    """Compila o LTFS patcheado."""
    print(">>> Building patched LTFS...")
    print(ssh(f"cd {LTFS_SRC} && make -j$(nproc) 2>&1 | tail -20", timeout=180))


def install_and_test() -> None:
    """Instala e testa o ltfsck patcheado."""
    print(">>> Installing patched ltfsck...")
    print(ssh(f"cp {LTFS_SRC}/src/utils/.libs/ltfsck /usr/local/bin/ltfsck-recovery 2>&1"))

    print(">>> Testing on sg1...")
    print(ssh(f"/usr/local/bin/ltfsck-recovery -l {TARGET_DEV} 2>&1", timeout=120))


def main() -> None:
    """Orquestra o processo de patch e recuperação."""
    print("=== LTFS Recovery Patch Tool ===")
    print(f"Target: {NAS_HOST} device {TARGET_DEV}")

    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        install_and_test()
        return

    apply_patches()
    build()
    install_and_test()


if __name__ == "__main__":
    main()
