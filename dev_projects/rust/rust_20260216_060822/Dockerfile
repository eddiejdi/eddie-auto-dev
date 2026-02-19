FROM rust:1.75-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*


RUN cargo add rust-agent
RUN cargo add jira-sdk
RUN cargo add tokio
RUN cargo add clap

COPY . .

CMD ["tail", "-f", "/dev/null"]
