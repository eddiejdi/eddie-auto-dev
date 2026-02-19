FROM golang:1.22-alpine

WORKDIR /app


RUN apk add --no-cache git gcc musl-dev


RUN go get github.com/gin-gonic/gin
RUN go get gorm.io/gorm
RUN go get github.com/joho/godotenv

COPY . .

CMD ["tail", "-f", "/dev/null"]
