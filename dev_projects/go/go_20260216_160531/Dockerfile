FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get net/http
RUN go get database/sql
RUN go get encoding/json

COPY . .

CMD ["tail", "-f", "/dev/null"]
