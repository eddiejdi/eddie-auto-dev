#!/usr/bin/env python3
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {'.git', 'venv', '.venv', '.venv_auto', 'eddie-copilot', 'dev_projects', 'solutions', 'backups', 'node_modules'}
TEXT_EXTS = {'.py', '.yml', '.yaml', '.md', '.txt', '.sh', '.ini', '.json', '.cfg'}

modified = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    # prune excluded dirs
    parts = Path(dirpath).relative_to(ROOT).parts
    if any(p in EXCLUDE_DIRS for p in parts):
        continue
    for fname in filenames:
        fpath = Path(dirpath) / fname
        if any(p in fpath.parts for p in EXCLUDE_DIRS):
            continue
        if fpath.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            s = fpath.read_text(encoding='utf-8')
        except Exception:
            continue
        orig = s
        # remove code-fence lines like ``` or ```python
        s = re.sub(r"^```(?:python)?\s*$\n?", "", s, flags=re.MULTILINE)
        # convert leading tabs to 4 spaces
        def repl_tabs(line):
            m = re.match(r"^(\t+)", line)
            if m:
                return ("    " * len(m.group(1))) + line[len(m.group(1)):]
            return line
        lines = s.splitlines(True)
        lines = [repl_tabs(l) for l in lines]
        s2 = ''.join(lines)
        if s2 != orig:
            fpath.write_text(s2, encoding='utf-8')
            modified.append(str(fpath.relative_to(ROOT)))

print("Modified files:")
for m in modified:
    print(m)
print(f"Total modified: {len(modified)}")

# run quick py_compile on changed py files
import subprocess
errors = []
for m in modified:
    if m.endswith('.py'):
        try:
            subprocess.run(['python3','-m','py_compile', str(ROOT / m)], check=True)
        except subprocess.CalledProcessError:
            errors.append(m)

if errors:
    print('\nPycompile errors in:')
    for e in errors:
        print(e)
    raise SystemExit(2)

if not modified:
    print('No changes needed.')

