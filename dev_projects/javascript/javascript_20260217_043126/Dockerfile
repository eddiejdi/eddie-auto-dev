FROM node:20-slim

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*


RUN npm init -y && npm install Node.js Express Jira REST API Client ESLint React Vue Next.js Fastify NestJS Jest

COPY . .

CMD ["tail", "-f", "/dev/null"]
