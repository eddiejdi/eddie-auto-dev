from __future__ import annotations

import json
from pathlib import Path


EXPECTED_EMAIL = 'edenilson.teixeira@rpa4all.com'
CHROME_SAMPLE = Path('/workspace/eddie-auto-dev/tools/tools/rpa4all-chrome-extension/sample-masses.json')
FIREFOX_SAMPLE = Path('/workspace/eddie-auto-dev/tools/tools/rpa4all-form-autofill-extension-unpacked/sample-masses.json')


def _load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text())['records']


def test_all_sample_records_use_rpa4all_email() -> None:
    """Todas as massas devem usar o email RPA4ALL definido para testes reais."""
    for path in [CHROME_SAMPLE, FIREFOX_SAMPLE]:
        records = _load_records(path)
        emails = [record.get('data', {}).get('email') for record in records if record.get('data', {}).get('email')]
        assert emails
        assert all(email == EXPECTED_EMAIL for email in emails)
