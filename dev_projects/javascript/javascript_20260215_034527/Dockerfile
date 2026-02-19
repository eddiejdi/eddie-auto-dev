FROM node:20-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*


RUN npm init -y && npm install javascript-agent jira-client-nodejs

COPY . .

CMD ["tail", "-f", "/dev/null"]
