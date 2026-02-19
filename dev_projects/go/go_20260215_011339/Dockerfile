FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get goagent
RUN go get jira-client
RUN go get http-server

COPY . .

CMD ["tail", "-f", "/dev/null"]
