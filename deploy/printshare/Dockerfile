FROM python:3.12-slim

WORKDIR /app

# Install CUPS client to allow submitting jobs with `lp`
RUN apt-get update && apt-get install -y --no-install-recommends cups-bsd && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py /app/

EXPOSE 8085

CMD ["gunicorn", "-b", "0.0.0.0:8085", "app:app", "--workers", "2"]
