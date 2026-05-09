import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import ipaddress

def generate_certs(cert_dir="./certs"):
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)

    print(f"🔄 Generating mTLS Certificates with SAN in {cert_dir}...")

    # 1. Generate CA
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"QuantSync-Internal-CA"),
    ])
    ca_cert = x509.CertificateBuilder().subject_name(
        ca_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        ca_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=3650)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    ).sign(ca_key, hashes.SHA256())

    # 2. Generate Server Cert
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"quantsync-ai-engine"),
    ])
    
    # Define SANs
    sans = [
        x509.DNSName(u"localhost"),
        x509.DNSName(u"quantsync-ai-engine"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    server_cert = x509.CertificateBuilder().subject_name(
        server_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        server_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName(sans), critical=False
    ).add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH, x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
    ).sign(ca_key, hashes.SHA256())

    # 3. Generate Client Cert
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    client_subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"quantsync-gateway"),
    ])
    client_cert = x509.CertificateBuilder().subject_name(
        client_subject
    ).issuer_name(
        ca_subject
    ).public_key(
        client_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).sign(ca_key, hashes.SHA256())

    # Helper to save
    def save_key(key, filename):
        with open(os.path.join(cert_dir, filename), "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

    def save_cert(cert, filename):
        with open(os.path.join(cert_dir, filename), "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

    save_key(ca_key, "ca.key")
    save_cert(ca_cert, "ca.crt")
    save_key(server_key, "server.key")
    save_cert(server_cert, "server.crt")
    save_key(client_key, "client.key")
    save_cert(client_cert, "client.crt")

    print(f"✅ [SUCCESS] Certificates generated with SANs in {cert_dir}")
    print("Files: ca.crt, ca.key, server.crt, server.key, client.crt, client.key")

if __name__ == "__main__":
    import sys
    path = "./certs"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    generate_certs(path)
