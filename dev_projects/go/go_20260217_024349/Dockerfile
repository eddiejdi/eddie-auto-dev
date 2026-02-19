FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go 1.14+

COPY . .

CMD ["tail", "-f", "/dev/null"]
