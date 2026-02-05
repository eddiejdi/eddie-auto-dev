FROM python:3.11-slim

WORKDIR /app

# Install common Python packages
RUN pip install --no-cache-dir \
    flask \
    flask-cors \
    gunicorn \
    numpy \
    pandas \
    matplotlib \
    requests \
    httpx \
    pydantic \
    python-dateutil \
    && rm -rf /root/.cache/pip

# Create non-root user for security
RUN useradd -m -s /bin/bash runner && \
    mkdir -p /tmp/code && \
    chown -R runner:runner /tmp/code

COPY app.py /app/app.py

EXPOSE 5000

# Run with gunicorn for production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--timeout", "60", "app:app"]
