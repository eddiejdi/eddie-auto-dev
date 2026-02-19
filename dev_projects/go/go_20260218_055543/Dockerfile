FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get net/http
RUN go get encoding/json
RUN go get log

COPY . .

CMD ["tail", "-f", "/dev/null"]
