FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY Russian_Trusted_Root_CA.crt /usr/local/share/ca-certificates/
COPY Russian_Trusted_Sub_CA_2024.crt /usr/local/share/ca-certificates/
COPY Russian_Trusted_Sub_CA.crt /usr/local/share/ca-certificates/

RUN update-ca-certificates

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn sam.main:app --host 0.0.0.0 --port 8000"]
