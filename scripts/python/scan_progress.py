#!/usr/bin/env python3
import os
import json
from pathlib import Path

data_file = Path.home() / ".scan_progress.json"

def load_progress():
    if data_file.exists():
        with open(data_file, "r") as f:
            return json.load(f)
    return {"checked": []}

def save_progress(progress):
    with open(data_file, "w") as f:
        json.dump(progress, f)

def scan_files(root, progress, limit=20):
    checked = set(progress["checked"])
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            fpath = os.path.relpath(os.path.join(dirpath, fname), root)
            if fpath not in checked and (fname.endswith(".py") or fname.endswith(".sh") or fname.endswith(".service") or fname == "README.md"):
                found.append(fpath)
                checked.add(fpath)
                if len(found) >= limit:
                    progress["checked"] = list(checked)
                    save_progress(progress)
                    return found
    progress["checked"] = list(checked)
    save_progress(progress)
    return found

if __name__ == "__main__":
    root = str(Path.home())
    progress = load_progress()
    files = scan_files(root, progress)
    print("Arquivos verificados nesta execução:")
    for f in files:
        print(f)
    if not files:
        print("Nenhum novo arquivo para verificar. Varredura completa!")

