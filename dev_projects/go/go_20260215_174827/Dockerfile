FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get go-agent
RUN go get jira-go-client

COPY . .

CMD ["tail", "-f", "/dev/null"]
