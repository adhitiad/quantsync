FROM python:3.13-slim

LABEL maintainer="Antigravity Senior Architect"
LABEL project="QuantSync AI Engine"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PYTHON_JIT=1
ENV TZ=UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# FIX: build context = root repo → path harus prefix quantsync-ai-engine/
# Pisah COPY requirements dulu untuk leverage Docker layer cache
COPY quantsync-ai-engine/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# FIX: copy seluruh isi quantsync-ai-engine/ langsung ke /app/
# sehingga server.py ada di /app/server.py dan PYTHONPATH=/app langsung valid
COPY quantsync-ai-engine/ .

# Proto files untuk gRPC stub (dibutuhkan oleh server.py)
COPY proto/ ./proto/

# Principle of Least Privilege
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 50051
EXPOSE 8081

# FIX: server.py sekarang ada di /app/server.py (bukan quantsync-ai-engine/server.py)
CMD ["python", "server.py"]
