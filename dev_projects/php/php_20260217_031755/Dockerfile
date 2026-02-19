FROM php:8.3-cli

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git unzip && rm -rf /var/lib/apt/lists/*
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer


RUN composer require PHP Agent Jira API

COPY . .

CMD ["tail", "-f", "/dev/null"]
