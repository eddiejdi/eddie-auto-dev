#!/usr/bin/env python3
"""Run Diretor and auto-validator in the same process so bus traffic is observable.
This starts `dev_agent.run_diretor_service.main()` and the validator loop in threads,
then attaches to the bus to print messages for debugging.
"""

import threading
import time
import pathlib
import importlib.util

repo = pathlib.Path(__file__).resolve().parents[1]
# load diretor module
spec = importlib.util.spec_from_file_location(
    "run_diretor", str(repo / "dev_agent" / "run_diretor_service.py")
)
diretor_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diretor_mod)

# load validator module
spec2 = importlib.util.spec_from_file_location(
    "auto_validator", str(repo / "tools" / "auto_validate_redirect.py")
)
val_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(val_mod)

# load bus for attach
spec_bus = importlib.util.spec_from_file_location(
    "agent_bus_local", str(repo / "specialized_agents" / "agent_communication_bus.py")
)
agent_bus = importlib.util.module_from_spec(spec_bus)
spec_bus.loader.exec_module(agent_bus)
get_communication_bus = agent_bus.get_communication_bus
MessageType = agent_bus.MessageType

bus = get_communication_bus()


def printer(msg):
    try:
        print("BUS MSG:", msg.to_dict())
    except Exception as e:
        print("printer error", e)


bus.subscribe(printer)

# Start diretor main in a thread
t1 = threading.Thread(target=diretor_mod.main, daemon=True)
# Start validator main (which will return on success) in a thread
# note: auto_validate_redirect.main expects to be run as script; call main()


def start_validator():
    try:
        val_mod.main(poll=15, timeout=3600)
    except SystemExit:
        pass


t2 = threading.Thread(target=start_validator, daemon=True)

print("Starting Diretor and validator threads (attach to bus)")

t1.start()
t2.start()

# keep main thread alive while threads run
try:
    while t1.is_alive() or t2.is_alive():
        time.sleep(1)
except KeyboardInterrupt:
    print("Interrupted")
