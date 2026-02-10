#!/usr/bin/env python3
"""
Generate a new admin password, update the OpenWebUI SQLite `auth` row,
save the plaintext to `/tmp/openwebui_admin_password.txt` (mode 600), and
send it via Telegram using /etc/eddie/telegram.env or provided args.

Usage (example):
  python3 specialized_agents/rotate_and_send_openwebui_admin.py \
    --db /var/lib/docker/volumes/open-webui/_data/webui.db \
    --email edenilson.teixeira@rpa4all.com

Requires: Python 3.8+, `bcrypt` installed in the environment that runs the script.
If `bcrypt` is missing, the script prints instructions to install it.
"""
import os
import sys
import argparse
import secrets
import sqlite3
import shutil
import stat
import json
import time
import subprocess


def read_token_and_chat(env_path='/etc/eddie/telegram.env'):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat = os.getenv('TELEGRAM_CHAT_ID')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('TELEGRAM_BOT_TOKEN=') and not token:
                        token = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if line.startswith('TELEGRAM_CHAT_ID=') and not chat:
                        chat = line.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    
    # Fallback: Secrets Agent
    if not token or not chat:
        try:
            from tools.secrets_loader import get_telegram_token, get_telegram_chat_id
            if not token:
                token = get_telegram_token() or token
            if not chat:
                chat = get_telegram_chat_id() or chat
        except Exception:
            pass
    
    return token, chat


def send_via_curl(token: str, chat_id: str, text: str, timeout: int = 15):
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        p = subprocess.Popen([
            'curl', '-s', '-X', 'POST', api,
            '--data-urlencode', f'text={text}',
            '-d', f'chat_id={chat_id}',
            '-d', 'parse_mode=HTML'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        return out.decode('utf-8', errors='ignore')
    except Exception as e:
        return json.dumps({'ok': False, 'error': str(e)})


def generate_password(nbytes: int = 24) -> str:
    # token_urlsafe yields longer output than nbytes; use for human-safe secret
    return secrets.token_urlsafe(nbytes)


def bcrypt_hash(password: str, rounds: int = 12) -> str:
    try:
        import bcrypt
    except Exception:
        print('Missing dependency: bcrypt. Install with: pip install bcrypt', file=sys.stderr)
        raise
    h = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds))
    return h.decode('utf-8')


def backup_db(db_path: str) -> str:
    ts = time.strftime('%Y%m%d%H%M%S')
    dst = f"{db_path}.bak-{ts}"
    shutil.copy2(db_path, dst)
    return dst


def update_auth_password(db_path: str, email: str, bcrypt_hash_str: str) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT id FROM auth WHERE email = ?', (email,))
    row = cur.fetchone()
    if not row:
        conn.close()
        print(f"User with email '{email}' not found in auth table.")
        return False
    cur.execute('UPDATE auth SET password = ?, active = 1 WHERE email = ?', (bcrypt_hash_str, email))
    conn.commit()
    conn.close()
    return True


def write_password_file(path: str, password: str):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(password + '\n')
    os.chmod(path, 0o600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True, help='Path to webui SQLite DB')
    parser.add_argument('--email', default='edenilson.teixeira@rpa4all.com', help='Admin email to update')
    parser.add_argument('--rounds', type=int, default=12, help='bcrypt rounds (work factor)')
    parser.add_argument('--chat-id', help='Telegram chat id (overrides /etc/eddie/telegram.env)')
    parser.add_argument('--token', help='Telegram bot token (overrides /etc/eddie/telegram.env)')
    parser.add_argument('--out', default='/tmp/openwebui_admin_password.txt', help='Path to write plaintext password')
    args = parser.parse_args()

    db_path = args.db
    if not os.path.exists(db_path):
        print('DB file not found:', db_path, file=sys.stderr)
        sys.exit(2)

    # Backup DB
    try:
        bak = backup_db(db_path)
        print('DB backed up to', bak)
    except Exception as e:
        print('Failed to create DB backup:', e, file=sys.stderr)
        sys.exit(3)

    # Generate password and hash
    pwd = generate_password(24)
    try:
        h = bcrypt_hash(pwd, rounds=args.rounds)
    except Exception:
        print('bcrypt not available. Install it and re-run the script.', file=sys.stderr)
        sys.exit(4)

    # Update DB
    ok = update_auth_password(db_path, args.email, h)
    if not ok:
        print('Did not update DB. Aborting.', file=sys.stderr)
        sys.exit(5)

    # Write plaintext to file (600)
    try:
        write_password_file(args.out, pwd)
        print('Wrote plaintext password to', args.out)
    except Exception as e:
        print('Failed to write password file:', e, file=sys.stderr)

    # Send via Telegram
    token = args.token
    chat = args.chat_id
    tkn, cht = read_token_and_chat()
    token = token or tkn
    chat = chat or cht or '11981193899'

    if not token or not chat:
        print('Telegram token or chat_id not found; skipping send. Set /etc/eddie/telegram.env or pass --token/--chat-id')
        sys.exit(0)

    text = f"Admin password for {args.email}:\n{pwd}\n\nRotate after use."
    print('Sending message to Telegram chat', chat)
    resp = send_via_curl(token, chat, text)
    print('Telegram API response:', resp)
    try:
        r = json.loads(resp)
        if r.get('ok'):
            # rename file to .sent
            try:
                os.rename(args.out, args.out + '.sent')
                print('Password file renamed to', args.out + '.sent')
            except Exception as e:
                print('Failed to rename password file:', e)
        else:
            print('Telegram returned error; password file left at', args.out)
    except Exception:
        print('Could not parse Telegram response; check network and token. Password file left at', args.out)


if __name__ == '__main__':
    main()
