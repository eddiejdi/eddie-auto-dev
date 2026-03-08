#!/bin/bash
# Corrige OLLAMA_HOST no github_agent_streamlit.py
sed -i 's/OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")/OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")/' /home/homelab/github-agent/github_agent_streamlit.py
echo "Corrigido OLLAMA_HOST (mantendo fallback para localhost) - prefira definir OLLAMA_HOST no ambiente"
grep -n "OLLAMA_HOST" /home/homelab/github-agent/github_agent_streamlit.py
