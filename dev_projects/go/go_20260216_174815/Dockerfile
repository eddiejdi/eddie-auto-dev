FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go 1.16+
RUN go get PostgreSQL
RUN go get MongoDB

COPY . .

CMD ["tail", "-f", "/dev/null"]
