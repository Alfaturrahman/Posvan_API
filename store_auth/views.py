import json
import bcrypt
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, transaction
from posvana_api.response import Response  # pastikan ini sesuai path
from datetime import datetime
import re

@csrf_exempt
def register_store_owner(request):
    if request.method != 'POST':
        return Response.badRequest(request, message="Method not allowed", messagetype='E')

    try:
        data = json.loads(request.body)

        required_fields = [
            "email", "name_owner", "no_nik", "no_hp", "store_name", "store_address",
            "description", "package_id", "statement_letter", "store_picture",
            "ktp_picture", "business_license", "submission_code", "no_virtual_account",
            "password", "start_date", "end_date"
        ]

        for field in required_fields:
            if not data.get(field):
                return Response.badRequest(request, message=f"{field} is required", messagetype='E')

        # Validasi format email
        if not is_valid_email(data["email"]):
            return Response.badRequest(request, message="Invalid email format", messagetype='E')

        # Validasi tanggal
        try:
            datetime.strptime(data["start_date"], "%Y-%m-%d")
            datetime.strptime(data["end_date"], "%Y-%m-%d")
        except ValueError:
            return Response.badRequest(request, message="Invalid date format. Expected YYYY-MM-DD", messagetype='E')

        hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.tbl_store_owners (
                        email,
                        name_owner,
                        no_nik,
                        no_hp,
                        store_name,
                        store_address,
                        description,
                        package_id,
                        statement_letter,
                        store_picture,
                        ktp_picture,
                        business_license,
                        submission_code,
                        created_at,
                        no_virtual_account,
                        payment_status,
                        account_status,
                        password,
                        is_active,
                        start_date,
                        end_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                """, [
                    data["email"],
                    data["name_owner"],
                    data["no_nik"],
                    data["no_hp"],
                    data["store_name"],
                    data["store_address"],
                    data["description"],
                    data["package_id"],
                    data["statement_letter"],
                    data["store_picture"],
                    data["ktp_picture"],
                    data["business_license"],
                    data["submission_code"],
                    "",
                    False,  # Payment status
                    "In Progress",  # Account status
                    hashed_password,
                    False,  # Active account
                    data["start_date"],
                    data["end_date"]
                ])

        return Response.ok(message="Store owner registered successfully", messagetype='S')

    except Exception as e:
        return Response.badRequest(request, message=f"Error during store owner registration: {str(e)}", messagetype='E')


def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email)
