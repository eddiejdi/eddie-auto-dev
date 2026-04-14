FROM python:3.11-slim

WORKDIR /app

# Copy kiosk HTML
COPY kiosk-dashboard.html /app/index.html

# Expose port
EXPOSE 8504

# Simple HTTP server
CMD ["python", "-m", "http.server", "8504", "--bind", "0.0.0.0"]
