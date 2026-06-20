#!/usr/bin/env python3
"""
Saneia o diretório de provisioning do Grafana desabilitando arquivos
JSON com UIDs duplicados, mantendo apenas o mais recente de cada UID.

Uso: python3 grafana_dedup_provisioning.py <provisioning_dir>
"""
import glob
import json
import os
import sys
import datetime


def main():
    prov_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    uid_map = {}

    for f in glob.glob(prov_dir + "/**/*.json", recursive=True):
        if ".disabled" in f or f.endswith(".bak") or f.endswith(".yml"):
            continue
        try:
            with open(f) as fh:
                d = json.load(fh)
            uid = d.get("uid") or d.get("dashboard", {}).get("uid")
            if uid:
                uid_map.setdefault(uid, []).append(f)
        except Exception:
            pass

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    any_disabled = False

    for uid, files in uid_map.items():
        if len(files) <= 1:
            continue
        # Mantém o mais recente; desabilita os demais
        files_by_mtime = sorted(files, key=os.path.getmtime, reverse=True)
        keep, *obsolete = files_by_mtime
        print(f"⚠️  UID [{uid}] — {len(files)} arquivos detectados:")
        print(f"  ✅ Mantendo (mais recente): {keep}")
        for old in obsolete:
            new_name = old + ".disabled." + ts
            os.rename(old, new_name)
            print(f"  🗑️  Desabilitado: {old} → {os.path.basename(new_name)}")
        any_disabled = True

    if not any_disabled:
        print("✅ Nenhum UID duplicado encontrado")


if __name__ == "__main__":
    main()
