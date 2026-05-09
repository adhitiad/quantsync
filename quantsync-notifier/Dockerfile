FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for mysqlclient if needed
RUN apt-get update && apt-get install -y \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY quantsync-notifier/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY quantsync-notifier/ /app/quantsync-notifier/
COPY proto/ /app/proto/

ENV PYTHONPATH=/app

CMD ["python", "quantsync-notifier/main.py"]
