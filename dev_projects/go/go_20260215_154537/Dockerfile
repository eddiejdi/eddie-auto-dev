FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go Agent
RUN go get Jira API
RUN go get HTTP server
RUN go get Testing framework

COPY . .

CMD ["tail", "-f", "/dev/null"]
