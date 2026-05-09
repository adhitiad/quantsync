# Build Stage
FROM golang:1.25-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git

# Copy go mod and sum
COPY quantsync-gateway/go.mod quantsync-gateway/go.sum ./
RUN go mod download

# Copy the rest of the backend and proto files
COPY quantsync-gateway/ .
COPY proto/ /app/proto/

# Build the application with maximum optimization
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o main ./main.go

# Run Stage
FROM alpine:latest

WORKDIR /app

# Create non-root user
RUN adduser -D -g '' appuser

COPY --from=builder /app/main .

# Ganti ownership ke appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["./main"]
