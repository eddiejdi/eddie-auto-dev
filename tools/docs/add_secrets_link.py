#!/usr/bin/env python3
import os
from pathlib import Path

root = Path(__file__).resolve().parents[2]
footer = "\n\n**Como obter secrets:** Consulte [docs/SECRETS_AGENT_USAGE.md](docs/SECRETS_AGENT_USAGE.md) para instruções de acesso ao Secrets Agent e boas práticas.\n"

count = 0
for p in root.rglob('*.md'):
    # skip the new doc itself
    if p.match('docs/SECRETS_AGENT_USAGE.md'):
        continue
    # skip files in .git
    if '.git' in p.parts:
        continue
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue
    if 'SECRETS_AGENT_USAGE.md' in text or 'Secrets Agent' in text:
        continue
    # append footer
    p.write_text(text + footer, encoding='utf-8')
    count += 1

print(f"Appended footer to {count} files")
