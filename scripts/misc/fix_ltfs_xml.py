#!/usr/bin/env python3
"""
LTFS XML validator and fixer.
Usage: fix_ltfs_xml.py <input.xml> <output.xml> [--validate-only]

Handles corruption types:
  1. Non-indented (0-indent) garbage lines inside <file> blocks
  2. Truncated timestamps ending with 'h>' or 's>' instead of 'Z</tagname>'
  3. Duplicate required tags (keeps last occurrence per <file> block)
  4. Missing required tags (adds defaults)

Block detection uses indentation, not XML depth counting, so nested
garbage <file> entries don't confuse the parser.
"""

import re, sys, argparse

REQUIRED_FILE_TAGS = [
    b'name', b'length', b'fileuid',
    b'creationtime', b'changetime', b'modifytime', b'accesstime',
    b'readonly', b'backuptime',
]

TIMESTAMP_DEFAULT = b'1970-01-01T00:00:00.000000000Z'
CORRUPT_TS_RE = re.compile(
    rb'^(\s*<(creationtime|changetime|modifytime|accesstime|backuptime)>)(.*?)([hs]>)\s*$'
)


def fix_truncated_ts(line):
    """
    Fix lines like:
      <creationtime>2024-03-10T20:38s>  ->  <creationtime>2024-03-10T20:38:00.000000000Z</creationtime>
    """
    m = CORRUPT_TS_RE.match(line)
    if not m:
        return line
    prefix = m.group(1)   # e.g. b'          <creationtime>'
    tag    = m.group(2)   # e.g. b'creationtime'
    value  = m.group(3)   # e.g. b'2024-03-10T20:38'
    v = value.decode('utf-8', errors='replace')
    if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$', v):
        v += ':00.000000000Z'
    elif re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', v):
        v += '.000000000Z'
    elif re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$', v):
        v += 'Z'
    else:
        v += 'Z'
    return prefix + v.encode() + b'</' + tag + b'>\n'


def collect_file_block(lines, start):
    """
    Collect a <file> block by matching indentation of the opening tag.
    Ignores any <file>/<directory> tags at different indent levels.
    Returns (block_lines, next_i).
    """
    opening = lines[start]
    indent = len(opening) - len(opening.lstrip(b' '))
    close_exact = b' ' * indent + b'</file>'

    block = [opening]
    j = start + 1
    while j < len(lines):
        bl = lines[j]
        if bl.rstrip(b'\r\n') == close_exact:
            block.append(bl)
            j += 1
            break
        block.append(bl)
        j += 1
    return block, j


def fix_file_block(block, verbose=False):
    """
    Validate and fix a single <file> block.
    Returns (fixed_block, change_count, issue_list).
    """
    issues = []
    changes = 0

    # 1. Fix truncated timestamps
    fixed = []
    for line in block:
        new_line = fix_truncated_ts(line)
        if new_line != line:
            changes += 1
            issues.append(f"truncated timestamp fixed: {line.strip()[:80].decode('utf-8','replace')}")
        fixed.append(new_line)
    block = fixed

    # 1b. Fix mismatched closing tags: <openTag>value</closeTag> where openTag != closeTag
    MISMATCH_RE = re.compile(rb'^(\s*<(\w+)>)(.*?)</(\w+)>\s*$')
    TS_TAGS = {b'creationtime', b'changetime', b'modifytime', b'accesstime', b'backuptime'}
    fixed = []
    for line in block:
        m = MISMATCH_RE.match(line)
        if m and m.group(2) != m.group(4):
            open_tag = m.group(2)
            raw_value = m.group(3)
            # Extract clean timestamp prefix before any stray '>'
            clean_v = raw_value.split(b'>')[0]
            v_str = clean_v.decode('utf-8', errors='replace')
            ts_m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', v_str)
            ts_m2 = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})', v_str) if not ts_m else None
            ts_m3 = re.match(r'(\d{4}-\d{2}-\d{2})', v_str) if not ts_m and not ts_m2 else None
            if ts_m:
                clean_v = ts_m.group(1).encode() + b'.000000000Z'
            elif ts_m2:
                clean_v = ts_m2.group(1).encode() + b':00.000000000Z'
            elif ts_m3 and open_tag in TS_TAGS:
                clean_v = ts_m3.group(1).encode() + b'T00:00:00.000000000Z'
            else:
                clean_v = TIMESTAMP_DEFAULT if open_tag in TS_TAGS else raw_value
            fixed_line = m.group(1) + clean_v + b'</' + open_tag + b'>\n'
            changes += 1
            issues.append(f"mismatched tag fixed: <{open_tag.decode()}> closed by </{m.group(4).decode()}>")
        else:
            fixed_line = line
        fixed.append(fixed_line)
    block = fixed

    # 1c. Fix timestamp tag values that are not valid ISO 8601 (stray '>' or garbage suffix)
    VALID_TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z$')
    TS_TAG_LINE_RE = re.compile(rb'^(\s*<(creationtime|changetime|modifytime|accesstime|backuptime)>)(.*?)</\2>\s*$')
    fixed = []
    for line in block:
        m = TS_TAG_LINE_RE.match(line)
        if m:
            value = m.group(3).decode('utf-8', errors='replace')
            if not VALID_TS_RE.match(value):
                clean = value.split('>')[0]
                tm = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', clean)
                tm2 = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})', clean) if not tm else None
                tm3 = re.match(r'(\d{4}-\d{2}-\d{2})', clean) if not tm and not tm2 else None
                if tm:
                    clean_v = tm.group(1).encode() + b'.000000000Z'
                elif tm2:
                    clean_v = tm2.group(1).encode() + b':00.000000000Z'
                elif tm3:
                    clean_v = tm3.group(1).encode() + b'T00:00:00.000000000Z'
                else:
                    clean_v = TIMESTAMP_DEFAULT
                tag = m.group(2)
                fixed_line = m.group(1) + clean_v + b'</' + tag + b'>\n'
                changes += 1
                issues.append(f"invalid ts value fixed: {value[:60]}")
            else:
                fixed_line = line
        else:
            fixed_line = line
        fixed.append(fixed_line)
    block = fixed

    # 2. Handle 0-indent XML lines (inside block, not first/last)
    # Extent attribute tags that may appear at 0-indent due to corruption
    EXTENT_ATTR_TAGS = {b'fileoffset', b'partition', b'startblock', b'byteoffset', b'bytecount'}
    open_indent_0 = len(block[0]) - len(block[0].lstrip(b' '))
    extent_attr_indent = b' ' * (open_indent_0 + 6)  # file(+0) + extentinfo(+2) + extent(+4) + attr(+6) = +12? No: 8+2=ei, 8+4=extent, 8+6=attr

    # Actually compute from a real example: <file> at 8sp → attr at 14sp = 8+6
    # Use open_indent + 6 for extent attrs
    in_extent = False
    out_block = [block[0]]
    for i in range(1, len(block) - 1):
        line = block[i]
        stripped = line.strip()
        leading = len(line) - len(line.lstrip(b' '))

        # Track extent context
        if stripped == b'<extent>':
            in_extent = True
        elif stripped == b'</extent>':
            in_extent = False

        if leading == 0 and stripped and stripped.startswith(b'<'):
            # Check if this is an extent attribute at wrong indent
            is_extent_attr = False
            for etag in EXTENT_ATTR_TAGS:
                if stripped.startswith(b'<' + etag + b'>') and stripped.endswith(b'</' + etag + b'>'):
                    is_extent_attr = True
                    break
            if is_extent_attr and in_extent:
                # Re-indent to correct position (file_open_indent + 6)
                fixed_line = extent_attr_indent + stripped + b'\n'
                out_block.append(fixed_line)
                changes += 1
                issues.append(f"extent attr re-indented: {stripped[:60].decode('utf-8','replace')}")
            else:
                # Genuine garbage line — remove
                changes += 1
                issues.append(f"garbage line removed: {stripped[:80].decode('utf-8','replace')}")
        else:
            out_block.append(line)
    if len(block) > 1:
        out_block.append(block[-1])
    block = out_block

    # 3. Deduplicate required tags (keep last occurrence per block)
    tag_positions = {}
    for i, line in enumerate(block):
        if i == 0 or i == len(block) - 1:
            continue
        stripped = line.strip()
        for tag in REQUIRED_FILE_TAGS:
            if stripped.startswith(b'<' + tag + b'>'):
                tag_positions.setdefault(tag, []).append(i)

    skip = set()
    for tag, positions in tag_positions.items():
        if len(positions) > 1:
            for pos in positions[:-1]:
                skip.add(pos)
                changes += 1
            issues.append(f"duplicate <{tag.decode()}> removed ({len(positions)-1} extras)")

    if skip:
        block = [line for i, line in enumerate(block) if i not in skip]

    # 4. Ensure required tags are present; add missing ones before <extentinfo>
    open_indent = len(block[0]) - len(block[0].lstrip(b' '))
    attr_indent = b' ' * (open_indent + 2)

    present = set()
    for line in block:
        s = line.strip()
        for tag in REQUIRED_FILE_TAGS:
            if s.startswith(b'<' + tag + b'>'):
                present.add(tag)

    insert_at = len(block) - 1  # default: before </file>
    for i, line in enumerate(block):
        if b'<extentinfo>' in line:
            insert_at = i
            break

    additions = []
    for tag in [b'readonly', b'backuptime']:
        if tag not in present:
            default = b'false' if tag == b'readonly' else TIMESTAMP_DEFAULT
            additions.append(attr_indent + b'<' + tag + b'>' + default + b'</' + tag + b'>\n')
            changes += 1
            issues.append(f"missing <{tag.decode()}> added")

    for ts_tag in [b'creationtime', b'changetime', b'modifytime', b'accesstime']:
        if ts_tag not in present:
            additions.append(attr_indent + b'<' + ts_tag + b'>' + TIMESTAMP_DEFAULT + b'</' + ts_tag + b'>\n')
            changes += 1
            issues.append(f"missing <{ts_tag.decode()}> added")

    if additions:
        block = block[:insert_at] + additions + block[insert_at:]

    return block, changes, issues


def validate_block(block):
    """Return list of issues found in block (read-only)."""
    _, _, issues = fix_file_block([l for l in block], verbose=False)
    return issues


def process(src, dst, validate_only=False):
    print(f"Reading {src}...")
    lines = open(src, "rb").readlines()
    print(f"  {len(lines)} lines, {sum(len(l) for l in lines):,} bytes")

    out = []
    i = 0
    files_total = 0
    files_with_issues = 0
    total_changes = 0

    while i < len(lines):
        if lines[i].strip() == b'<file>':
            block, next_i = collect_file_block(lines, i)
            files_total += 1
            if validate_only:
                issues = validate_block(block)
                if issues:
                    files_with_issues += 1
                    name = next((bl.strip()[6:-7].decode('utf-8','replace')
                                 for bl in block if bl.strip().startswith(b'<name>')), '?')
                    print(f"  Line {i+1} [{name}]: {'; '.join(issues[:3])}")
                out.extend(block)
                i = next_i
            else:
                fixed, changes, issues = fix_file_block(block)
                out.extend(fixed)
                if changes:
                    files_with_issues += 1
                    total_changes += changes
                    if files_with_issues <= 20:
                        name = next((bl.strip()[6:-7].decode('utf-8','replace')
                                     for bl in fixed if bl.strip().startswith(b'<name>')), '?')
                        print(f"  Line {i+1} [{name}]: {', '.join(str(x) for x in issues[:5])}")
                i = next_i
        else:
            out.append(lines[i])
            i += 1

    bt  = sum(1 for l in out if b'<backuptime>' in l)
    ro  = sum(1 for l in out if b'<readonly>'   in l)
    fc  = sum(1 for l in out if l.strip() == b'<file>')
    print(f"\nFiles: {files_total} total, {files_with_issues} with issues")
    if not validate_only:
        print(f"Total changes: {total_changes}")
    print(f"Output stats: {fc} <file>, {bt} <backuptime>, {ro} <readonly>")

    if not validate_only:
        print(f"\nWriting {dst}...")
        with open(dst, "wb") as f:
            f.writelines(out)
        out_size = sum(len(l) for l in out)
        print(f"  {out_size:,} bytes ({len(out):,} lines)")
    print("Done.")


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('input',  help='Input LTFS index XML')
    p.add_argument('output', help='Output fixed XML (ignored with --validate-only)')
    p.add_argument('--validate-only', action='store_true', help='Only report issues, do not write output')
    args = p.parse_args()
    process(args.input, args.output, validate_only=args.validate_only)
