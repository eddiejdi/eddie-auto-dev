FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements_advisor.txt ./
RUN pip install --no-cache-dir -r requirements_advisor.txt
COPY advisor_agent.py ./
EXPOSE 8085
ENV PORT=8085
CMD ["uvicorn", "advisor_agent:app", "--host", "0.0.0.0", "--port", "8085"]
