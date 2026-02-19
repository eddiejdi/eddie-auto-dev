FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Go 1.13+
RUN go get Goroutine
RUN go get Channel
RUN go get HTTP Client
RUN go get File I/O

COPY . .

CMD ["tail", "-f", "/dev/null"]
