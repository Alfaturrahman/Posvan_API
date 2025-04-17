# utils/jwt_helper.py
import jwt
import datetime
from django.conf import settings

def generate_jwt_token(user_data):
    payload = {
        "user_id": user_data["user_id"],
        "email": user_data["email"],
        "role_id": user_data["role_id"],
        "role_name": user_data["role_name"],
        "reference_id": user_data["reference_id"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=settings.JWT_EXP_DELTA_SECONDS)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def decode_jwt_token(token):
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired")
    except jwt.InvalidTokenError:
        raise Exception("Invalid token")
