FROM node:20-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN npm install -g typescript ts-node


RUN npm init -y && npm install @types/node @typescript/agent jira-js-client

COPY . .

CMD ["tail", "-f", "/dev/null"]
