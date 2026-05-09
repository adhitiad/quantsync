FROM python:3.13-slim

# Meta-information
LABEL maintainer="Antigravity Senior Architect"
LABEL project="QuantSync AI Engine"

# Environment variables to optimize Python performance
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PYTHON_JIT=1
ENV TZ=UTC

WORKDIR /app

# Install minimal system dependencies for numerical libraries and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install core dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Leverage Docker cache by copying requirements first
COPY requirements.txt .

# Install dependencies
# Using CPU-only PyTorch to reduce image size for AI Trading Hub constraints
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Security: Apply Principle of Least Privilege (Rootless)
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# gRPC (Standard) and WebSocket (Secure/Custom) ports
EXPOSE 50051
EXPOSE 8443

# Healthcheck to ensure the gRPC server is responding (requires grpc_health_probe in production, or simple curl/python check)
# HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
#     CMD python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('localhost', 50051))"

# Entrypoint: Launch the AI Engine gRPC Gateway
CMD ["python", "server.py"]
