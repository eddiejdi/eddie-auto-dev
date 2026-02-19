FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go Agent
RUN go get Jira API library
RUN go get HTTP client library

COPY . .

CMD ["tail", "-f", "/dev/null"]
