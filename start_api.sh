#!/bin/bash
cd /home/homelab/myClaude/specialized_agents
/home/homelab/.local/bin/uvicorn api:app --host 0.0.0.0 --port 8503
