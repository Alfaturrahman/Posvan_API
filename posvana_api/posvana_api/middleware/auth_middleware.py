from functools import wraps
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from posvana_api.utils.jwt_helper import decode_jwt_token

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                token_type, token = auth_header.split()
                if token_type.lower() != 'bearer':
                    raise Exception("Invalid token format")
                
                # Decode token untuk mendapatkan payload
                payload = decode_jwt_token(token)
                request.user_data = payload
            except Exception as e:
                return JsonResponse({
                    "status_code": 401,
                    "message": str(e),
                    "messagetype": "E",
                    "data": []
                }, status=401)
        else:
            request.user_data = None

def jwt_required(view_func):
    """
    Decorator untuk memastikan bahwa request memiliki token JWT yang valid.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Mengecek apakah request memiliki user_data (valid token)
        if not request.user_data:
            return JsonResponse({
                "status_code": 401,
                "message": "Authorization header missing or invalid",
                "messagetype": "E",
                "data": []
            }, status=401)
        
        # Lanjutkan ke view jika token valid
        return view_func(request, *args, **kwargs)

    return _wrapped_view
