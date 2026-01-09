#!/bin/bash
# Corrige OLLAMA_HOST no github_agent_streamlit.py
sed -i 's/OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")/OLLAMA_HOST = os.getenv("OLLAMA_HOST", "192.168.15.2")/' /home/homelab/github-agent/github_agent_streamlit.py
echo "Corrigido OLLAMA_HOST para 192.168.15.2"
grep -n "OLLAMA_HOST" /home/homelab/github-agent/github_agent_streamlit.py
