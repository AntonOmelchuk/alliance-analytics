import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

# 1. Generate private key SECP256R1 (NIST P-256)
private_key = ec.generate_private_key(ec.SECP256R1())

# 2. Get bytes (32 bytes)
private_value = private_key.private_numbers().private_value
private_bytes = private_value.to_bytes(32, byteorder='big')

# 3. Public key
public_key = private_key.public_key()
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

# 4. Encoded to URL-safe Base64
vapid_private_key = base64.urlsafe_b64encode(private_bytes).decode('utf-8').rstrip('=')
vapid_public_key = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

print("\n=== ВСТАВ ЦІ КЛЮЧІ В .env ===\n")
print(f'VAPID_PUBLIC_KEY="{vapid_public_key}"')
print(f'VAPID_PRIVATE_KEY="{vapid_private_key}"')
print("\n===============================\n")