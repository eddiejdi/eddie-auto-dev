#!/usr/bin/env python3
"""
Migrate secrets from local .env files to Bitwarden.
Usage:
  python3 migrate_to_bw.py [--dry-run] [--file path/to/.env]
  
Environment:
  BW_SESSION or read from /tmp/bw_session.txt
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def get_bw_session():
    """Get BW_SESSION from env or /tmp/bw_session.txt"""
    session = os.environ.get("BW_SESSION")
    if session:
        return session
    
    session_file = Path("/tmp/bw_session.txt")
    if session_file.exists():
        return session_file.read_text().strip()
    
    raise RuntimeError("BW_SESSION not defined and /tmp/bw_session.txt not found")

def create_bw_item(name, notes, session):
    """Create a Secure Note in Bitwarden."""
    # Use bw encode + create instead of raw JSON
    try:
        result = subprocess.run(
            ["bw", "create", "item", json.dumps({"type": 3, "name": name, "notes": notes})],
            env={**os.environ, "BW_SESSION": session},
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)

def migrate_file(file_path, session, dry_run=False):
    """Migrate a .env file to Bitwarden."""
    file_path = Path(file_path).expanduser()
    if not file_path.exists():
        print(f"Arquivo não encontrado: {file_path}")
        return False
    
    print(f"Processando {file_path}")
    file_name = file_path.name
    
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    success_count = 0
    fail_count = 0
    
    for line in lines:
        line = line.strip()
        # Skip comments and blank lines
        if not line or line.startswith("#"):
            continue
        
        if "=" not in line:
            item_name = f"{file_name}:line"
            item_value = line
        else:
            key, val = line.split("=", 1)
            item_name = f"{file_name}:{key.strip()}"
            item_value = val.strip()
        
        if dry_run:
            print(f"DRY: criar item '{item_name}' (valor length: {len(item_value)})")
        else:
            success, msg = create_bw_item(item_name, item_value, session)
            if success:
                print(f"✓ {item_name}")
                success_count += 1
            else:
                print(f"✗ {item_name}: {msg[:100]}")
                fail_count += 1
    
    print(f"Resultado: {success_count} sucesso, {fail_count} falha")
    return fail_count == 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate secrets to Bitwarden")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--file", default=str(Path.home() / ".secrets" / ".env.jira"))
    
    args = parser.parse_args()
    
    try:
        session = get_bw_session()
        success = migrate_file(args.file, session, dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(2)
