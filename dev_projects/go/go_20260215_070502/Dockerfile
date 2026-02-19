FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go Agent
RUN go get Jira API
RUN go get HTTP Server
RUN go get API REST
RUN go get Testing with go test

COPY . .

CMD ["tail", "-f", "/dev/null"]
