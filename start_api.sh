#!/bin/bash
cd /home/eddie/myClaude/specialized_agents
/home/eddie/.local/bin/uvicorn api:app --host 0.0.0.0 --port 8503
