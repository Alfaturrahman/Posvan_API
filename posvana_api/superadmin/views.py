import json
import bcrypt
import uuid
from django.views.decorators.csrf import csrf_exempt
from django.db import connection, transaction
from posvana_api.response import Response  # pastikan ini sesuai path
from django.core.files.storage import FileSystemStorage  # Importing FileSystemStorage
from datetime import datetime
import datetime
from django.utils import timezone   
from common.pagination_helper import paginate_data
from common.transaction_helper import *
from posvana_api.utils.jwt_helper import *
import re

#Pengajuan Toko (SUPERADMIN)

@jwt_required
@csrf_exempt
def show_store_owners(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():

            status_param = request.GET.get("status")
            tanggal_param = request.GET.get("tanggal")  

            filters = {}

            status_mapping = {
                "Selesai": "Accepted",
                "Diproses": "In Progress",
                "Ditolak": "Rejected"
            }

            if status_param and status_param != "Semua Status":
                mapped_status = status_mapping.get(status_param)
                if mapped_status:
                    filters["account_status"] = mapped_status

            tanggal_param = request.GET.get("tanggal")
            if tanggal_param:
                try:
                    tanggal_obj = datetime.strptime(tanggal_param, "%m/%d/%Y").date()
                    filters["DATE(created_at)"] = tanggal_obj  # 
                except ValueError:
                    pass  

            store_owners = get_data(
                table_name="tbl_store_owners",
                filters=filters
            )

            return Response.ok(
                data=store_owners,
                message="List data telah tampil",
                messagetype="S"
            )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(
            request,
            message=str(e),
            messagetype="E"
        )

@jwt_required
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

@jwt_required
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
                "account_status": "Accepted",
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

@jwt_required
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

@jwt_required
@csrf_exempt
def dashboard_pengajuan(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():
            
            total_pengajuan = count_data(
                table_name="tbl_store_owners",
            )
            total_diproses = count_data(
                table_name="tbl_store_owners",
                filters={"account_status" : "In Progress" }
            )

            total_diterima = count_data(
                table_name="tbl_store_owners",
                filters={"account_status" : "Accepted" }
            )
            
            total_ditolak = count_data(
                table_name="tbl_store_owners",
                filters={"account_status" : "Rejected" }
            )

            result = {
                "total_pengajuan": total_pengajuan,
                "total_diproses": total_diproses,
                "total_diterima": total_diterima,
                "total_ditolak": total_ditolak,
            }

            return Response.ok(data=result, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
# Daftar Paket

@jwt_required
@csrf_exempt
def list_package(request):
    try:
        with transaction.atomic():
            
            List_Paket = get_data(
                table_name="tbl_packages",
            )

            return Response.ok(data=List_Paket, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def insert_package(request):
    try:
        validate_method(request, "POST")
        with transaction.atomic():
            json_data = json.loads(request.body)
            user_id = request.user.get("user_id")

            required_fields = ["package_name", "duration", "price", "description"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(
                        request,
                        message=f"Field '{field}' wajib diisi",
                        messagetype="E"
                    )
            
            # Format tanggal (mungkin menggunakan waktu saat ini untuk created_at dan update_at)
            now = timezone.now()

            # Data yang akan di-insert ke tabel tbl_packages
            data_to_insert = {
                "user_id" : user_id,
                "package_name": json_data["package_name"],
                "duration": json_data["duration"],
                "price": json_data["price"],
                "description": json_data["description"],
                "created_at":  now,
                "update_at": now,
            }

            # Insert data ke tabel tbl_packages dan ambil ID-nya
            package_id = insert_get_id_data(
                table_name="tbl_packages",
                data=data_to_insert,
                column_id="package_id"
            )

            return Response.ok(data={"package_id": package_id},message="Paket berhasil ditambahkan",messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_package(request, package_id):
    try:
        validate_method(request, "PUT")
        with transaction.atomic():
            # Ambil data dari request body
            json_data = json.loads(request.body)

            # Validasi data
            required_fields = ["package_name", "duration", "price", "description"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(
                        request,
                        message=f"Field '{field}' wajib diisi",
                        messagetype="E"
                    )

            # Cek apakah package_id yang diberikan ada dalam database
            existing_package = get_data(
                table_name="tbl_packages",
                filters={"package_id": package_id}
            )
            if not existing_package:
                return Response.badRequest(
                    request,
                    message=f"Paket dengan ID {package_id} tidak ditemukan",
                    messagetype="E"
                )

            # Format tanggal (update)
            now = datetime.datetime.now()

            # Data yang akan di-update
            data_to_update = {
                "package_name": json_data["package_name"],
                "duration": json_data["duration"],
                "price": json_data["price"],
                "description": json_data["description"],
                "update_at": now
            }

            # Update data di tabel tbl_packages
            update_data(
                table_name="tbl_packages",
                data=data_to_update,
                filters={"package_id": package_id}
            )

            return Response.ok(
                message=f"Paket dengan ID {package_id} berhasil diperbarui",
                messagetype="S"
            )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def delete_package(request, package_id):
    try:
        with transaction.atomic():
            
            delete_data(
                table_name="tbl_packages",
                filters={"package_id" : package_id }
            )

            return Response.ok(data=package_id, message=f"Delete data dengan ID {package_id} Berhasil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def list_master_features(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():
            
            List_Paket = get_data(
                table_name="tbl_masters_features",
            )

            return Response.ok(data=List_Paket, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

# Dashboard

@jwt_required
@csrf_exempt
def dashboard_data_store(request):
    try:
        with transaction.atomic():
            
            search = request.GET.get("search", None)

            list_toko_terdaftar = get_data(
                table_name="tbl_store_owners",
                search=search,
                search_columns=["store_name"]
            )

            jumlah_toko_terdaftar = count_data(
                table_name="tbl_store_owners",
            )

            jumlah_toko_terdaftar_aktif = count_data(
                table_name="tbl_store_owners",
                filters={"is_active" : True }
            )
            
            jumlah_toko_terdaftar_tidak_aktif = count_data(
                table_name="tbl_store_owners",
                filters={"is_active" : False }
            )

            dashboard_data_store = {
                "List_toko_terdaftar" : list_toko_terdaftar ,
                "jumlah_toko_terdaftar" : jumlah_toko_terdaftar ,
                "jumlah_toko_terdaftar_aktif" : jumlah_toko_terdaftar_aktif ,
                "jumlah_toko_terdaftar_tidak_aktif" : jumlah_toko_terdaftar_tidak_aktif ,
            }

            return Response.ok(data=dashboard_data_store, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

 
