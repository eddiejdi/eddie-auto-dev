#!/bin/bash
cd /home/home-lab/myClaude/specialized_agents
/home/home-lab/.local/bin/uvicorn api:app --host 0.0.0.0 --port 8503
