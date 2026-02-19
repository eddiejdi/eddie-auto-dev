FROM python:3.12-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir Flask SQLAlchemy Jinja2 Celery

COPY . .

CMD ["tail", "-f", "/dev/null"]
