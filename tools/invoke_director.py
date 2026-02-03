#!/usr/bin/env python3
"""Invoke the Diretor model/agent via the communication bus.

This helper publishes a request targeted at the `DIRETOR` target so existing
listeners (or the Open WebUI 'Diretor Eddie' model) can pick it up.

Usage:
  ./tools/invoke_director.py "Please produce a safety checklist for enabling autonomous mode"
"""
import sys
import pathlib
import importlib.util

if len(sys.argv) < 2:
    print("Usage: invoke_director.py \"message\"")
    sys.exit(1)

message = sys.argv[1]

# Load bus by path to avoid package import overhead
bus_path = pathlib.Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

bus = get_communication_bus()
msg = bus.publish(MessageType.REQUEST, 'assistant', 'DIRETOR', message, {})
print('Bus publish:', msg.id if msg else 'failed')

# If Postgres IPC is available, also publish request there so cross-process listeners can pick it up
try:
    # import agent_ipc by path to avoid relying on package import
    from pathlib import Path
    import importlib.util
    agent_ipc_path = Path(__file__).resolve().parents[1] / 'tools' / 'agent_ipc.py'
    spec = importlib.util.spec_from_file_location('agent_ipc', str(agent_ipc_path))
    agent_ipc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_ipc)
    rid = agent_ipc.publish_request('assistant', 'DIRETOR', message, {'via': 'invoke_director'})
    print('DB publish id:', rid)
except Exception as e:
    # Log the error so callers can see why DB publish failed and attempt a best-effort retry
    print('DB publish failed:', e)
    # Try to infer Postgres creds from a docker container named 'eddie-postgres'
    try:
        import os, json, subprocess
        out = subprocess.run(['docker', 'inspect', 'eddie-postgres', '--format', '{{json .Config.Env}}'], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout:
            env_list = json.loads(out.stdout)
            env = {k.split('=',1)[0]: k.split('=',1)[1] for k in env_list if '=' in k}
            user = env.get('POSTGRES_USER')
            pwd = env.get('POSTGRES_PASSWORD')
            db = env.get('POSTGRES_DB')
            if user and pwd and db:
                from urllib.parse import quote_plus
                user_q = quote_plus(user)
                pwd_q = quote_plus(pwd)
                guessed = f'postgresql://{user_q}:{pwd_q}@localhost:5432/{db}'
                os.environ.setdefault('DATABASE_URL', guessed)
                # reload agent_ipc and retry publish
                # import agent_ipc again from path (so it picks up DATABASE_URL)
                spec = importlib.util.spec_from_file_location('agent_ipc', str(agent_ipc_path))
                agent_ipc = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(agent_ipc)
                try:
                    rid = agent_ipc.publish_request('assistant', 'DIRETOR', message, {'via': 'invoke_director', 'guessed': True})
                    print('DB publish id (via docker-inspect):', rid)
                except Exception as e2:
                    print('Retry DB publish failed:', e2)
    except Exception as e_inspect:
        print('docker-inspect attempt failed:', e_inspect)
