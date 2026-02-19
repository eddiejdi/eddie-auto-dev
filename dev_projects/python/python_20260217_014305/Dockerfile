FROM python:3.12-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir Flask Flask-SQLAlchemy Flask-RESTful

COPY . .

CMD ["tail", "-f", "/dev/null"]
