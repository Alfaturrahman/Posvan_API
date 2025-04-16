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

        hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Step 1: Insert into tbl_store_owners
                cursor.execute("""
                    INSERT INTO public.tbl_store_owners (
                        email, name_owner, no_nik, no_hp, store_name, store_address,
                        description, package_id, statement_letter, store_picture,
                        ktp_picture, business_license, submission_code,
                        created_at, no_virtual_account, payment_status,
                        account_status, is_active, start_date, end_date
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s)
                    RETURNING store_id
                """, [
                    data["email"], data["name_owner"], data["no_nik"], data["no_hp"],
                    data["store_name"], data["store_address"], data["description"], data["package_id"],
                    data["statement_letter"], data["store_picture"], data["ktp_picture"],
                    data["business_license"], data["submission_code"],
                    data["no_virtual_account"], False, "In Progress", False,
                    data["start_date"], data["end_date"]
                ])

                store_id = cursor.fetchone()[0]

                # Step 2: Insert into tbl_user
                cursor.execute("""
                    INSERT INTO public.tbl_user (
                        user_id, email, "Password", role_id, created_at, role_name, reference_id
                    ) VALUES (
                        %s, %s, %s, %s, NOW(), %s, %s
                    )
                """, [
                    store_id,  # user_id disamakan dengan store_id (atau bisa generate ID lain)
                    data["email"],
                    hashed_password,
                    2,                # role_id (misal: 2 untuk 'store_owner')
                    'store_owner',
                    store_id          # reference_id ke tbl_store_owners
                ])

        return Response.ok(message="Store owner registered successfully", messagetype='S')

    except Exception as e:
        return Response.badRequest(request, message=f"Error during registration: {str(e)}", messagetype='E')

@csrf_exempt
def login_user(request):
    if request.method != 'POST':
        return Response.badRequest(request, message="Method not allowed", messagetype='E')

    try:
        data = json.loads(request.body)
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return Response.badRequest(request, message="Email and password are required", messagetype='E')

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, email, "Password", role_id, role_name, reference_id
                FROM public.tbl_user
                WHERE email = %s
            """, [email])
            user = cursor.fetchone()

        if not user:
            return Response.badRequest(request, message="User not found", messagetype='E')

        user_id, email, hashed_password, role_id, role_name, reference_id = user

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            return Response.badRequest(request, message="Invalid credentials", messagetype='E')

        return Response.ok(
            message="Login successful",
            messagetype='S',
            data={
                "user_id": user_id,
                "email": email,
                "role_id": role_id,
                "role_name": role_name,
                "reference_id": reference_id
            }
        )

    except Exception as e:
        return Response.badRequest(request, message=f"Error during login: {str(e)}", messagetype='E')

