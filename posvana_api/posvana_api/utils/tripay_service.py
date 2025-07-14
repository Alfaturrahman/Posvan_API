import os
import requests
import hashlib
import hmac
import requests

TRIPAY_API_KEY = os.getenv('TRIPAY_API_KEY') or 'DEV-EUnLArWekqFALJ9K8hxad9Ef7nciSkBK0p4iJFJZ'
TRIPAY_PRIVATE_KEY = os.getenv('TRIPAY_PRIVATE_KEY') or 'Rvu5O-EHVZ4-aD7Hj-iJQyh-snu61'
TRIPAY_MERCHANT_CODE = os.getenv('TRIPAY_MERCHANT_CODE') or 'T39300'
TRIPAY_BASE_URL = "https://tripay.co.id/api-sandbox"

def create_transaction(payload):
    url = f"{TRIPAY_BASE_URL}/transaction/create"
    headers = {"Authorization": f"Bearer {TRIPAY_API_KEY}"}
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    if response.status_code != 200 or data.get('success') is not True:
        raise Exception(data.get('message', 'Gagal membuat transaksi Tripay'))
    return data['data']

def create_signature(merchant_ref, amount):
    payload = TRIPAY_MERCHANT_CODE + merchant_ref + str(int(amount))
    return hmac.new(
        TRIPAY_PRIVATE_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_callback_signature(raw_body, callback_signature):
    expected_signature = hmac.new(
        TRIPAY_PRIVATE_KEY.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(callback_signature, expected_signature)

def get_transaction_detail(reference):
    api_key = "DEV-EUnLArWekqFALJ9K8hxad9Ef7nciSkBK0p4iJFJZ"
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"https://tripay.co.id/api-sandbox/transaction/detail?reference={reference}"
    response = requests.get(url, headers=headers)
    data = response.json()
    if data.get('success'):
        return data.get('data', {})
    return {}


