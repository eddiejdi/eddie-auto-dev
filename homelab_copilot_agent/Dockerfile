FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY homelab_copilot_agent/requirements_advisor.txt ./
RUN pip install --no-cache-dir -r requirements_advisor.txt

# Copiar agente
COPY homelab_copilot_agent/advisor_agent.py ./

# Copiar módulo IPC (PostgreSQL)
COPY tools/agent_ipc.py ./tools/
RUN touch ./tools/__init__.py

# Copiar bus de comunicação
COPY specialized_agents/agent_communication_bus.py ./specialized_agents/
RUN touch ./specialized_agents/__init__.py

EXPOSE 8085
ENV PORT=8085
CMD ["uvicorn", "advisor_agent:app", "--host", "0.0.0.0", "--port", "8085"]
