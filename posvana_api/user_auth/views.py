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
from posvana_api.utils.jwt_helper import *
from posvana_api.utils.email_template import render_email_template
from django.core.mail import EmailMessage

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
                SELECT user_id, email, "Password", role_id, role_name, reference_id
                FROM public.tbl_user
                WHERE email = %s
            """, [email])
            user = cursor.fetchone()

        if not user:
            return Response.badRequest(request, message="User not found", messagetype='E')

        user_id, email, hashed_password, role_id, role_name, reference_id = user

        # Cek tambahan hanya untuk store_owner
        if role_name == "store_owner":
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT account_status, is_active
                    FROM public.tbl_store_owners
                    WHERE email = %s
                """, [email])
                store_data = cursor.fetchone()

            if store_data:
                account_status, is_active = store_data

                if account_status == "In Progress":
                    return Response.badRequest(request, message="Your account is under review", messagetype='E')

                if not is_active:
                    return Response.badRequest(request, message="Please complete the payment", messagetype='E')

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            return Response.badRequest(request, message="Invalid credentials", messagetype='E')
        
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
                    3,                  
                    'customer',
                    user_id             
                ])

        return Response.ok(message="Customer registered successfully", messagetype='S')

    except Exception as e:
        return Response.badRequest(request, message=f"Error during customer registration: {str(e)}", messagetype='E')

@csrf_exempt
def change_password(request):
    try:
        if request.method != "PUT":
            return Response.badRequest(request, message="Invalid HTTP method, expected PUT", messagetype="E")
        
        json_data = json.loads(request.body)

        # Ambil data dari request
        user_id = json_data.get("user_id")
        old_password = json_data.get("oldPassword")
        new_password = json_data.get("newPassword")
        confirm_password = json_data.get("confirmPassword")

        # Validasi data yang diterima
        if not all([user_id, old_password, new_password, confirm_password]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")
        
        if len(new_password) < 6:
            return Response.badRequest(request, message="New password must be at least 6 characters", messagetype="E")
        
        if new_password != confirm_password:
            return Response.badRequest(request, message="Confirmation password does not match new password", messagetype="E")

        # Ambil data user dari database berdasarkan user_id
        user_data = first_data(
            table_name="tbl_user",
            filters={"user_id": user_id}
        )

        if not user_data:
            return Response.badRequest(request, message="User not found", messagetype="E")
        
        if "Password" not in user_data:
            return Response.badRequest(request, message="Password field not found in database", messagetype="E")

        stored_password = user_data["Password"]

        # Verifikasi password lama
        if not bcrypt.checkpw(old_password.encode('utf-8'), stored_password.encode('utf-8')):
            return Response.badRequest(request, message="Old Password tidak sesuai", messagetype="E")

        # Hash password baru
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE tbl_user 
                SET "Password" = %s, update_at = NOW()
                WHERE user_id = %s
                """,
                [hashed_new_password, user_id]
            )

        # Response sukses
        return Response.ok(
            message="Password updated successfully",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message="Error while updating password: " + str(e), messagetype="E")