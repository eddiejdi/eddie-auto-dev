#!/bin/bash
# Script para iniciar Streamlit specialized_agents na porta 8502
cd /home/homelab/myClaude
source venv/bin/activate
exec streamlit run specialized_agents/streamlit_app.py --server.port 8502 --server.address 0.0.0.0 --server.headless true
