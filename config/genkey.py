from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from base64 import b64encode

private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=1024
)
pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
print(b64encode(pem).decode('utf-8'))