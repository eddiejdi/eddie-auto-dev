FROM node:20-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*


RUN npm init -y && npm install JavaScript Agent Jira SDK Node.js Express Fastify NestJS Jest ESLint React Vue Next.js Docker

COPY . .

CMD ["tail", "-f", "/dev/null"]
