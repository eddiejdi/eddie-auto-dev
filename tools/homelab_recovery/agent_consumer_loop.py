#!/usr/bin/env python3
import time
import json
from pathlib import Path

QUEUE = Path('/tmp/agent_queue')
CONSUMED = QUEUE / 'consumed'
CONSUMED.mkdir(parents=True, exist_ok=True)
LOG = Path('/tmp/agent_consumer_loop.log')

SLEEP = 5

def process_file(f: Path):
    issue = f.stem.split('_',1)[1]
    try:
        data = json.load(open(f,'r',encoding='utf-8'))
    except Exception as e:
        LOG.write_text(LOG.read_text() + f"\nErro lendo {f}: {e}")
        return
    # Simular trabalho
    time.sleep(1)
    ack = f.with_suffix('.ack')
    ack.write_text(json.dumps({'issue':issue,'consumed_at':time.time(),'processor':'agent-consumer-loop'}, indent=2))
    dest = CONSUMED / f.name
    f.rename(dest)
    LOG.write_text(LOG.read_text() + f"\nProcessed {issue} -> {dest}")


def main():
    LOG.write_text('Agent consumer loop started at ' + time.ctime() + '\n')
    while True:
        files = sorted(QUEUE.glob('rca_EA-*.json'))
        if not files:
            time.sleep(SLEEP)
            continue
        for f in files:
            process_file(f)
        time.sleep(SLEEP)

if __name__ == '__main__':
    main()
