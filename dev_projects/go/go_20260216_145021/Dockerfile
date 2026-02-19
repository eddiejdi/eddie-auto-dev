FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get net/http
RUN go get database/sql
RUN go get github.com/gin-gonic/gin

COPY . .

CMD ["tail", "-f", "/dev/null"]
