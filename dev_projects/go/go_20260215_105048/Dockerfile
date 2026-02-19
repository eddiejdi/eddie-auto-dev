FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go Agent
RUN go get Jira API
RUN go get Goroutines e channels
RUN go get HTTP servers e APIs REST

COPY . .

CMD ["tail", "-f", "/dev/null"]
