FROM python:3.13-slim

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY quantsync-notifier/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY quantsync-notifier/ /app/quantsync-notifier/
COPY proto/ /app/proto/

ENV PYTHONPATH=/app

CMD ["python", "quantsync-notifier/main.py"]
