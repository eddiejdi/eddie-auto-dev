#!/usr/bin/env python3
"""Monitor de respostas do DIRETOR e ações de correção automática.

Usage: python3 tools/monitor_diretor.py
"""
from datetime import datetime, timedelta
import time
import subprocess
# Load bus module by path to avoid import errors
import importlib.util
from pathlib import Path
bus_path = Path(__file__).resolve().parents[1] / 'specialized_agents' / 'agent_communication_bus.py'
spec = importlib.util.spec_from_file_location('agent_bus_local', str(bus_path))
agent_bus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType
log_response = agent_bus.log_response
log_error = agent_bus.log_error

CHECK_SCRIPTS = ['check_diretor_status.py', 'check_functions.py', 'check_model.py']


def run_check_scripts():
    outputs = []
    for c in CHECK_SCRIPTS:
        try:
            p = subprocess.run(['python3', c], capture_output=True, text=True, timeout=120)
            outputs.append(f"\n== {c} ==\n{p.stdout}\n{p.stderr}")
        except Exception as ex:
            outputs.append(f"\n== {c} exception ==\n{ex}")
    return outputs


def run_pytest():
    try:
        p = subprocess.run(['pytest', '-q'], capture_output=True, text=True, timeout=300)
        return '\n== pytest ==\n' + p.stdout + '\n' + p.stderr
    except Exception as ex:
        return '\n== pytest exception ==\n' + str(ex)


def main(timeout_seconds: int = 600):
    bus = get_communication_bus()
    start = datetime.now()
    deadline = start + timedelta(seconds=timeout_seconds)
    seen = set()
    print('Monitor started, listening for DIRETOR responses until', deadline.isoformat())
    while datetime.now() < deadline:
        msgs = bus.get_messages(limit=200, message_types=[MessageType.RESPONSE, MessageType.ERROR], source='DIRETOR', since=start)
        new = [m for m in msgs if m.id not in seen]
        if new:
            for m in new:
                seen.add(m.id)
                ts = m.timestamp.isoformat()
                print(f"[{ts}] {m.message_type.value.upper()} from {m.source} -> {m.target}: {m.content}")
                with open(f"/tmp/diretor_msg_{m.id}.txt", 'w') as f:
                    f.write(f"{ts} {m.message_type.value} {m.source} {m.target}\n{m.content}\n\nMETADATA:\n{m.metadata}\n")
                text = m.content.lower()
                if any(k in text for k in ['erro', 'falha', 'failed', 'fail', 'problem', 'broken', 'exception']):
                    print('Detected error keywords — running diagnostics...')
                    diagnostics = []
                    diagnostics.append(run_pytest())
                    diagnostics.extend(run_check_scripts())
                    diag_text = '\n'.join(diagnostics)
                    with open('/tmp/diretor_diagnostics.txt', 'w') as f:
                        f.write(diag_text)
                    summary = 'Found error keywords; ran diagnostics (pytest + checks). Results saved to /tmp/diretor_diagnostics.txt.'
                    log_response('assistant', 'DIRETOR', summary, original_message_id=m.id)
                    # If tests failed, send an error log
                    if 'FAILED' in diag_text or 'Traceback' in diag_text or 'ERROR' in diag_text:
                        log_error('assistant', 'Diagnostics found failing tests or errors; see /tmp/diretor_diagnostics.txt', original_message_id=m.id)
                    else:
                        log_response('assistant', 'DIRETOR', 'Diagnostics completed with no test failures.', original_message_id=m.id)
                else:
                    log_response('assistant', 'DIRETOR', 'Received your message, thank you. No error keywords detected.', original_message_id=m.id)
        time.sleep(5)
    print('Monitor finished (timeout)')


if __name__ == '__main__':
    main()