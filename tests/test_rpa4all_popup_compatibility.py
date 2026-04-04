from __future__ import annotations

import json
import subprocess
from pathlib import Path

POPUP_PATH = Path('/workspace/eddie-auto-dev/tools/tools/rpa4all-chrome-extension/popup.js')
SAMPLE_PATH = Path('/workspace/eddie-auto-dev/tools/tools/rpa4all-chrome-extension/sample-masses.json')


def _run_popup_harness(script_body: str) -> dict:
    """Executa popup.js em sandbox Node e retorna JSON com os resultados do teste."""
    harness = f"""
const fs = require('fs');
const vm = require('vm');
const popupSource = fs.readFileSync('{POPUP_PATH.as_posix()}', 'utf8');
const sample = JSON.parse(fs.readFileSync('{SAMPLE_PATH.as_posix()}', 'utf8'));

function makeNode() {{
  return {{
    textContent: '',
    style: {{}},
    value: '',
    disabled: false,
    innerHTML: '',
    href: '',
    checked: false,
    appendChild() {{}},
    addEventListener() {{}},
  }};
}}

const sandbox = {{
  console,
  __RPA4ALL_POPUP_TEST__: true,
  setTimeout() {{}},
  clearTimeout() {{}},
  fetch: async () => ({{ ok: true, json: async () => sample }}),
  chrome: {{
    runtime: {{
      getManifest: () => ({{ version: '1.2.0' }}),
      openOptionsPage() {{}},
      sendMessage(_message, callback) {{ callback({{ ok: true, records: [] }}); }},
      lastError: null,
    }},
    storage: {{
      local: {{
        get(_keys, callback) {{ callback({{}}); }},
        set(_data, callback) {{ callback(); }},
      }},
    }},
    tabs: {{
      query(_query, callback) {{ callback([]); }},
      sendMessage(_tabId, _message, callback) {{ callback({{ ok: true, result: {{ filled: 0, totalKeys: 0 }} }}); }},
    }},
    scripting: {{
      executeScript(_opts, callback) {{ callback([{{ result: null }}]); }},
    }},
  }},
  document: {{
    getElementById(_id) {{ return makeNode(); }},
    createElement(_tag) {{ return makeNode(); }},
  }},
}};
sandbox.globalThis = sandbox;
vm.runInNewContext(popupSource, sandbox, {{ filename: 'popup.js' }});
const exported = sandbox.__RPA4ALL_POPUP_EXPORTS;
{script_body}
"""
    result = subprocess.run(
        ['node', '-e', harness],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_marketing_records_are_incompatible_with_storage_page() -> None:
    """Registros de marketing nao devem ser considerados compativeis em pagina storage."""
    result = _run_popup_harness(
        """
const records = sample.records.filter((record) => record.id.startsWith('marketing-'));
const pageInfo = { url: 'https://www.rpa4all.com/storage-request.html', markers: ['storage-request-form'] };
const best = exported.findBestRecordForPage(records, pageInfo);
console.log(JSON.stringify({
  profile: exported.getPageProfile(pageInfo),
  compatible: best.compatible,
  score: best.score,
  bestId: best.record ? best.record.id : null,
}));
"""
    )
    assert result == {
        'profile': 'storage',
        'compatible': False,
        'score': 0,
        'bestId': 'marketing-001',
    }


def test_storage_records_win_on_storage_page() -> None:
    """Quando ha registros storage, o melhor match deve ser compativel com a pagina storage."""
    result = _run_popup_harness(
        """
const pageInfo = { url: 'https://www.rpa4all.com/storage-request.html', markers: ['storage-request-form'] };
const best = exported.findBestRecordForPage(sample.records, pageInfo);
console.log(JSON.stringify({
  compatible: best.compatible,
  bestId: best.record ? best.record.id : null,
  profile: exported.getPageProfile(pageInfo),
}));
"""
    )
    assert result['profile'] == 'storage'
    assert result['compatible'] is True
    assert result['bestId'].startswith('storage-')
