FROM rust:1.75-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*


RUN cargo add tokio
RUN cargo add serde
RUN cargo add reqwest
RUN cargo add jira-rs-client

COPY . .

CMD ["tail", "-f", "/dev/null"]
