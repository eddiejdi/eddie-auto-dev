FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get goagent
RUN go get jira-go
RUN go get github.com/stretchr/testify/assert

COPY . .

CMD ["tail", "-f", "/dev/null"]
