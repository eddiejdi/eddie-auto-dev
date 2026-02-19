FROM mcr.microsoft.com/dotnet/sdk:8.0

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*



COPY . .

CMD ["tail", "-f", "/dev/null"]
