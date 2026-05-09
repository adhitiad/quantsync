#!/bin/bash
set -e

# Directory for certificates
CERT_DIR="./certs"
mkdir -p $CERT_DIR

echo "Generating mTLS Certificates with SAN (Subject Alternative Names)..."

# 1. Generate CA key and certificate
openssl genrsa -out $CERT_DIR/ca.key 4096
openssl req -x509 -new -nodes -key $CERT_DIR/ca.key -sha256 -days 3650 -out $CERT_DIR/ca.crt -subj "/CN=QuantSync-Internal-CA"

# Configuration for SAN
CAT <<EOF > $CERT_DIR/san.cnf
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = quantsync-ai-engine

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = quantsync-ai-engine
IP.1 = 127.0.0.1
EOF

# 2. Generate Server key and CSR
openssl genrsa -out $CERT_DIR/server.key 4096
openssl req -new -key $CERT_DIR/server.key -out $CERT_DIR/server.csr -config $CERT_DIR/san.cnf

# Sign Server certificate with CA and SAN
openssl x509 -req -in $CERT_DIR/server.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key \
    -CAcreateserial -out $CERT_DIR/server.crt -days 365 -sha256 \
    -extensions v3_req -extfile $CERT_DIR/san.cnf

# 3. Generate Client key and CSR
openssl genrsa -out $CERT_DIR/client.key 4096
openssl req -new -key $CERT_DIR/client.key -out $CERT_DIR/client.csr -subj "/CN=quantsync-gateway"

# Sign Client certificate with CA
openssl x509 -req -in $CERT_DIR/client.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key \
    -CAcreateserial -out $CERT_DIR/client.crt -days 365 -sha256

# Cleanup temp config
rm $CERT_DIR/san.cnf

# Set permissions
chmod 600 $CERT_DIR/*.key
chmod 644 $CERT_DIR/*.crt

echo "✅ Certificates generated with SAN in $CERT_DIR"

