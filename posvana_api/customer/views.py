import json
import bcrypt
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, transaction
from posvana_api.response import Response  # pastikan ini sesuai path
from django.core.files.storage import FileSystemStorage  # Importing FileSystemStorage
from datetime import datetime
from django.utils import timezone   
from common.pagination_helper import paginate_data
from common.transaction_helper import *
from posvana_api.utils.jwt_helper import jwt_required
import re
from django.http.multipartparser import MultiPartParser

#Dashboard (STORE OWNER)

@jwt_required
@csrf_exempt
def data_toko(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():
            user = request.user  
            email = request.user.get("email")

            data_toko = execute_query(
                """
                    SELECT * FROM public.v_store_owners;
                """,
            )

            return Response.ok(data=data_toko, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
