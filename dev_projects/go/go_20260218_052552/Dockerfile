FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get Goroutines
RUN go get Channels
RUN go get HTTP servers
RUN go get RESTful APIs

COPY . .

CMD ["tail", "-f", "/dev/null"]
