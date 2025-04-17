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
from posvana_api.utils.jwt_helper import generate_jwt_token
import re

@csrf_exempt
def show_store_owners(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():
            
            show_store_owners = get_data(
                table_name="tbl_store_owners",
            )

            paginated_store_owner = paginate_data(request, show_store_owners)

            return Response.ok(data=paginated_store_owner, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@csrf_exempt
def detail_store_owners(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():

            store_id = request.GET.get("store_id")

            print(store_id)
            
            detail_store_owners = get_data(
                table_name="tbl_store_owners",
                filters={"store_id" : store_id}
            )
            return Response.ok(data=detail_store_owners, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@csrf_exempt
def validate_store_owner(request):
    try:
        validate_method(request, "PUT")
        store_id = request.GET.get("store_id")

        if not store_id:
            return Response.badRequest(request, message="store_id wajib diisi", messagetype="E")

        # Check if data exists
        if not exists_data(table_name="tbl_store_owners", filters={"store_id": store_id}):
            return Response.badRequest(request, message="Store owner tidak ditemukan", messagetype="E")

        # Update account_status
        update_data(
            table_name="tbl_store_owners",
            data={
                "account_status": "Sudah Divalidasi",
                "update_at": timezone.now()
            },
            filters={"store_id": store_id}
        )

        # Ambil email dan virtual account
        owner_data = get_data(
            table_name="tbl_store_owners",
            filters={"store_id": store_id}
        )

        if not owner_data:
            return Response.badRequest(request, message="Data store owner tidak ditemukan", messagetype="E")

        # Ambil data pertama dari list
        owner_data = owner_data[0]

        email = owner_data.get("email")
        virtual_account = owner_data.get("no_virtual_account")

        print(email,virtual_account)

        # Kirim email (dummy send_email function)
        send_email(
            to=email,
            subject="Virtual Account Anda",
            message=f"Terima kasih, akun Anda telah divalidasi.\nBerikut nomor virtual account Anda: {virtual_account}"
        )

        return Response.ok(message="Akun berhasil divalidasi & email VA telah dikirim", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

def send_email(to, subject, message):
    from django.core.mail import send_mail
    send_mail(
        subject,
        message,
        "noreply@namaprojectmu.com",  # sender
        [to],
        fail_silently=False,
    )

@csrf_exempt
def verify_payment(request):
    try:
        validate_method(request, "PUT")
        
        # Ambil store_id dari parameter URL (query params)
        store_id = request.GET.get("store_id")

        if not store_id:
            return Response.badRequest(request, message="store_id wajib diisi", messagetype="E")

        # Cek apakah data store owner ada
        if not exists_data(table_name="tbl_store_owners", filters={"store_id": store_id}):
            return Response.badRequest(request, message="Store owner tidak ditemukan", messagetype="E")

        # Update status payment_status dan is_active
        print("[DEBUG] Melakukan update payment_status ke True dan is_active ke True")
        update_data(
            table_name="tbl_store_owners",
            data={
                "payment_status": True,
                "is_active": True,
                "update_at": timezone.now()
            },
            filters={"store_id": store_id}
        )

        return Response.ok(message="Pembayaran berhasil diverifikasi & status akun diupdate", messagetype="S")

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

