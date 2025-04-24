# utils/jwt_helper.py

import jwt
import datetime
from functools import wraps
from django.conf import settings
from django.http import JsonResponse
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

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
    except ExpiredSignatureError:
        raise Exception("Token sudah kedaluwarsa")
    except InvalidTokenError:
        raise Exception("Token tidak valid")

def jwt_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JsonResponse({
                "status_code": 401,
                "message": "Authorization token tidak ditemukan",
                "messagetype": "E"
            }, status=401)

        token = auth_header.split(" ")[1]

        try:
            user_data = decode_jwt_token(token)
        except Exception as e:
            return JsonResponse({
                "status_code": 401,
                "message": str(e),
                "messagetype": "E"
            }, status=401)

        # Inject ke request.user agar natural digunakan di view
        request.user = user_data

        return view_func(request, *args, **kwargs)

    return _wrapped_view
