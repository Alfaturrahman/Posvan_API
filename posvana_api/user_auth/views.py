import json
import bcrypt
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, transaction
from posvana_api.response import Response  # pastikan ini sesuai path
from django.core.files.storage import FileSystemStorage  # Importing FileSystemStorage
from datetime import datetime
from posvana_api.utils.jwt_helper import generate_jwt_token
import re

@csrf_exempt
def register_store_owner(request):
    if request.method != 'POST':
        return Response.badRequest(request, message="Method not allowed", messagetype='E')

    try:
        data = request.POST

        required_fields = [
            "email", "name_owner", "no_nik", "no_hp", "store_name", "store_address",
            "description", "package_id", "submission_code", "no_virtual_account", "start_date", "end_date"
        ]

        for field in required_fields:
            if not data.get(field):
                return Response.badRequest(request, message=f"{field} is required", messagetype='E')

        # Cek apakah email sudah ada di tbl_user
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM public.tbl_user WHERE email = %s", [data["email"]])
            email_count = cursor.fetchone()[0]

        if email_count > 0:
            return Response.badRequest(request, message="Email is already registered", messagetype='E')

        # File handling
        store_picture = request.FILES.get('store_picture')
        ktp_picture = request.FILES.get('ktp_picture')
        statement_letter = request.FILES.get('statement_letter')
        business_license = request.FILES.get('business_license')

        fs = FileSystemStorage()
        store_picture_path = fs.save(store_picture.name, store_picture)
        ktp_picture_path = fs.save(ktp_picture.name, ktp_picture)
        statement_letter_path = fs.save(statement_letter.name, statement_letter)

        if business_license:
            business_license_path = fs.save(business_license.name, business_license)
        else:
            business_license_path = ""

        # Hash password
        hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with transaction.atomic():
            with connection.cursor() as cursor:
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
                    statement_letter_path, store_picture_path, ktp_picture_path,
                    business_license_path, data["submission_code"],
                    data["no_virtual_account"], False, "In Progress", False,
                    data["start_date"], data["end_date"]
                ])

                store_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO public.tbl_user (
                        user_id, email, "Password", role_id, created_at, role_name, reference_id
                    ) VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                """, [
                    store_id,
                    data["email"],
                    hashed_password,
                    2,
                    'store_owner',
                    store_id
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
                SELECT u.user_id, u.email, u."Password", u.role_id, u.role_name, u.reference_id,
                       s.account_status, s.is_active
                FROM public.tbl_user u
                JOIN public.tbl_store_owners s ON u.email = s.email
                WHERE u.email = %s
            """, [email])
            user = cursor.fetchone()

        if not user:
            return Response.badRequest(request, message="User not found", messagetype='E')

        user_id, email, hashed_password, role_id, role_name, reference_id, account_status, is_active = user

        

        # Mengecek status akun
        if account_status == "In Progress":
            return Response.badRequest(request, message="Your account is under review", messagetype='E')
        
        if not is_active:
            return Response.badRequest(request, message="Please complete the payment", messagetype='E')
        
        # Periksa apakah password cocok
        if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            return Response.badRequest(request, message="Invalid credentials", messagetype='E')

        # Jika status valid, buat token JWT
        token = generate_jwt_token({
            "user_id": user_id,
            "email": email,
            "role_id": role_id,
            "role_name": role_name,
            "reference_id": reference_id
        })

        return Response.ok(
            message="Login successful",
            messagetype='S',
            data={
                "token": token,
                "user": {
                    "user_id": user_id,
                    "email": email,
                    "role_id": role_id,
                    "role_name": role_name,
                    "reference_id": reference_id
                }
            }
        )

    except Exception as e:
        return Response.badRequest(request, message=f"Error during login: {str(e)}", messagetype='E')

@csrf_exempt
def register_customer(request):
    if request.method != 'POST':
        return Response.badRequest(request, message="Method not allowed", messagetype='E')

    try:
        data = json.loads(request.body)
        required_fields = ["email", "password", "name",]

        for field in required_fields:
            if not data.get(field):
                return Response.badRequest(request, message=f"{field} is required", messagetype='E')

        hashed_password = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Optional: insert to tbl_customers kalau kamu punya
                # cursor.execute("""INSERT INTO public.tbl_customers (name, no_wa, email, created_at) VALUES (%s, %s, %s, NOW()) RETURNING customer_id""", [data["name"], data["no_wa"], data["email"]])
                # customer_id = cursor.fetchone()[0]

                # Kalau tidak ada tabel customer, buat ID sendiri
                cursor.execute("SELECT COALESCE(MAX(user_id), 0) + 1 FROM public.tbl_user")
                user_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO public.tbl_user (
                        user_id, email, "Password", role_id, created_at, role_name, reference_id
                    ) VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                """, [
                    user_id,
                    data["email"],
                    hashed_password,
                    3,                  # role_id untuk customer
                    'customer',
                    user_id             # reference_id = user_id (atau customer_id kalau ada tabelnya)
                ])

        return Response.ok(message="Customer registered successfully", messagetype='S')

    except Exception as e:
        return Response.badRequest(request, message=f"Error during customer registration: {str(e)}", messagetype='E')
