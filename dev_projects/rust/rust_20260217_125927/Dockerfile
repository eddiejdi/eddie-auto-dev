FROM rust:1.75-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*



COPY . .

CMD ["tail", "-f", "/dev/null"]
