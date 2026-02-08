#!/usr/bin/env python3
"""CI watcher: monitora check runs de PRs abertos e publica atualizações no bus.

Uso: roda em background (nohup) e registra alterações em /tmp/ci_watcher_state.json
e logs em /tmp/ci_watcher.log. Reusa `tools/invoke_director.py` para publicar no bus.
"""
import time
import json
import subprocess
import os
import sys

OWNER = 'eddiejdi'
REPO = 'eddie-auto-dev'
STATE_FILE = '/tmp/ci_watcher_state.json'
LOG_FILE = '/tmp/ci_watcher.log'
POLL_INTERVAL = int(os.environ.get('CI_WATCHER_POLL', '30'))


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(line)
    print(line, end='')


def gh_pr_list():
    # returns list of dicts with number,title,headRefOid
    try:
        out = subprocess.check_output(['gh', 'pr', 'list', '--state', 'open', '--json', 'number,title,headRefOid'], text=True)
        return json.loads(out)
    except Exception as e:
        log(f'gh pr list failed: {e}')
        return []


def get_check_runs_for_sha(sha):
    try:
        api = f"/repos/{OWNER}/{REPO}/commits/{sha}/check-runs"
        out = subprocess.check_output(['gh', 'api', api], text=True)
        data = json.loads(out)
        return data.get('check_runs', [])
    except Exception as e:
        log(f'gh api check-runs failed for {sha}: {e}')
        return []


def summarize_check_runs(checks):
    if not checks:
        return {'state': 'none', 'failed': 0, 'total': 0}
    total = len(checks)
    failed = sum(1 for c in checks if c.get('conclusion') in ('failure','cancelled','timed_out','action_required'))
    in_progress = any(c.get('status') != 'completed' for c in checks)
    if failed:
        state = 'failure'
    elif in_progress:
        state = 'in_progress'
    else:
        state = 'success'
    return {'state': state, 'failed': failed, 'total': total}


def publish_update(pr_number, title, summary):
    msg = f"CI Update: PR #{pr_number} '{title}' state={summary['state']} failed={summary['failed']}/{summary['total']}"
    try:
        subprocess.run(['python3', 'tools/invoke_director.py', msg], check=False)
        log(f'Published update for PR #{pr_number}: {msg}')
    except Exception as e:
        log(f'Failed to publish update: {e}')


def send_telegram(message: str):
    """Send a Telegram message if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set."""
    bot = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not bot or not chat:
        return False
    try:
        # Use curl to avoid extra Python deps
        payload = message.replace('"', '\\"')
        cmd = [
            'curl', '-s', '-X', 'POST',
            f"https://api.telegram.org/bot{bot}/sendMessage",
            '-d', f"chat_id={chat}", '-d', f"text={payload}"
        ]
        subprocess.run(cmd, check=False)
        log('Telegram alert sent')
        return True
    except Exception as e:
        log(f'Telegram send failed: {e}')
        return False


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            return {}
    return {}


def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        log(f'Failed to save state: {e}')


def main():
    log('CI watcher starting')
    state = load_state()
    while True:
        prs = gh_pr_list()
        for pr in prs:
            num = pr.get('number')
            title = pr.get('title') or ''
            sha = pr.get('headRefOid')
            if not sha:
                continue
            checks = get_check_runs_for_sha(sha)
            summary = summarize_check_runs(checks)
            key = str(num)
            prev = state.get(key, {})
            if prev.get('state') != summary['state'] or prev.get('failed') != summary['failed']:
                publish_update(num, title, summary)
                # If the PR now has failing checks (and it wasn't failing before), escalate to Diretor
                if summary.get('state') == 'failure' and prev.get('state') != 'failure':
                    # collect failing check names and links
                    failing_runs = [
                        (c.get('name') or 'unnamed', c.get('html_url') or c.get('details_url') or '')
                        for c in checks
                        if c.get('conclusion') in ('failure','cancelled','timed_out','action_required')
                    ]
                    if failing_runs:
                        formatted = []
                        for name, url in failing_runs[:10]:
                            if url:
                                formatted.append(f"{name} ({url})")
                            else:
                                formatted.append(name)
                        fail_list = '; '.join(formatted)
                        more = '' if len(failing_runs) <= 10 else f' (+{len(failing_runs)-10} more)'
                    else:
                        fail_list = 'unspecified checks'
                        more = ''
                    pr_url = f"https://github.com/{OWNER}/{REPO}/pull/{num}"
                    director_msg = (
                        f"CI BREAK: PR #{num} '{title}' has failing checks ({summary['failed']}/{summary['total']}): {fail_list}{more}."
                        f" Logs and run pages: see the links above. Please triage and assign to the responsible team. PR: {pr_url}"
                    )
                    try:
                        subprocess.run(['python3', 'tools/invoke_director.py', director_msg], check=False)
                        log(f'Escalated PR #{num} failure to Diretor')
                    except Exception as e:
                        log(f'Failed to escalate to Diretor for PR #{num}: {e}')
                state[key] = summary
                save_state(state)
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('CI watcher exiting on keyboard interrupt')
