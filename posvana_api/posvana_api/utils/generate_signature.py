import hmac
import hashlib

# Ganti ini pakai TRIPAY_PRIVATE_KEY punyamu
TRIPAY_PRIVATE_KEY = 'Rvu5O-EHVZ4-aD7Hj-iJQyh-snu61'

# Data callback sesuai yang mau kamu test
reference = "DEV-T39300258360AEJIC"
total_amount = 10000
status = "PAID"

# Payload sesuai dokumentasi tripay: reference + total_amount + status
payload = reference + str(total_amount) + status

# Generate signature
signature = hmac.new(
    TRIPAY_PRIVATE_KEY.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

print("Generated signature:", signature)
