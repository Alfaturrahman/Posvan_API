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
import re
import os
from posvana_api.utils.email_template import render_email_template
from django.core.mail import EmailMessage
from posvana_api.utils.notification_helper import insert_notification

#Pengajuan Toko (SUPERADMIN)

@jwt_required
@csrf_exempt
def show_store_owners(request):
    try:
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
                    tanggal_obj = datetime.datetime.strptime(tanggal_param, "%m/%d/%Y").date()
                    filters["DATE(created_at)"] = tanggal_obj  # 
                except ValueError:
                    pass  

            store_owners = get_data(
                table_name="tbl_store_owners",
                filters=filters,
                order_by="created_at DESC"
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
        with transaction.atomic():

            store_id = request.GET.get("store_id")

            detail_store_owners = first_data(
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
        if request.method != "PUT":
            return Response.badRequest(request, message="Method tidak diizinkan", messagetype="E")
        
        store_id = request.GET.get("store_id")
        status = request.GET.get("status")  # "Done" atau "Reject"

        if not store_id:
            return Response.badRequest(request, message="store_id wajib diisi", messagetype="E")

        if not status:
            return Response.badRequest(request, message="status wajib diisi", messagetype="E")

        if status not in ["Done", "Reject"]:
            return Response.badRequest(request, message="status tidak valid", messagetype="E")

        if not exists_data(table_name="tbl_store_owners", filters={"store_id": store_id}):
            return Response.badRequest(request, message="Store owner tidak ditemukan", messagetype="E")

        # Update status validasi store_owner
        update_data(
            table_name="tbl_store_owners",
            data={
                "account_status": status,
                "update_at": timezone.now()
            },
            filters={"store_id": store_id}
        )

        owner_data = get_data(
            table_name="tbl_store_owners",
            filters={"store_id": store_id}
        )
        if not owner_data:
            return Response.badRequest(request, message="Data store owner tidak ditemukan", messagetype="E")

        owner_data = owner_data[0]
        email = owner_data.get("email")
        full_name = owner_data.get("name_owner")
        store_name = owner_data.get("store_name")

        if status == "Done":
            notif_title = "Akun Toko Divalidasi"
            notif_message = f"Akun toko {store_name} Anda telah berhasil divalidasi dan aktif."
            notif_type = "store_validation"

            # Kirim email validasi sukses
            context = {
                "full_name": full_name,
                "store_name": store_name,
                "email": email,
                "password": owner_data.get("password", "-"),
                "package_duration": owner_data.get("package_duration", "-"),
                "package_type": owner_data.get("package_type", "-"),
                "package_price": owner_data.get("package_price", "-"),
                "login_url": "https://posvana.com/login",
                "virtual_account": owner_data.get("no_virtual_account")
            }

            template_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'posvana_api', 'posvana_api', 'templates', 'email', 'email_store_validated.html')
            )
            email_body = render_email_template(template_path, context)

            send_email(
                to=email,
                subject="Akun Toko Anda Telah Divalidasi!",
                message=email_body,
                content_type='text/html'
            )
        
        else:  # status == "Reject"
            notif_title = "Pengajuan Akun Ditolak"
            notif_message = f"Pengajuan akun toko {store_name} Anda ditolak. Silakan daftar ulang."
            notif_type = "store_validation_reject"

            # Kirim email penolakan
            context = {
                "full_name": full_name,
                "store_name": store_name,
                "email": email,
                "registration_url": "https://posvana.com/daftar-ulangan"
            }

            template_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'posvana_api', 'posvana_api', 'templates', 'email', 'email_store_rejected.html')
            )
            email_body = render_email_template(template_path, context)

            send_email(
                to=email,
                subject="Pengajuan Akun Toko Anda Ditolak",
                message=email_body,
                content_type='text/html'
            )

        # Insert notifikasi ke store_owner
        insert_notification(
            user_id=store_id,
            target_role='store_owner',
            notif_type=notif_type,
            title=notif_title,
            message=notif_message,
            data=json.dumps({"store_id": store_id, "status": status})
        )

        return Response.ok(
            message=f"Akun berhasil {status.lower()} & email VA telah dikirim" if status == "Done" else "Akun berhasil ditolak, email pemberitahuan telah dikirim",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

def send_email(to, subject, message, content_type='text/plain'):
    email = EmailMessage(
        subject=subject,
        body=message,
        to=[to],
    )
    if content_type == 'text/html':
        email.content_subtype = 'html'
    email.send()

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

        owner_data = get_data(
            table_name="tbl_store_owners",
            filters={"store_id": store_id}
        )
        if not owner_data:
            return Response.badRequest(request, message="Data store owner tidak ditemukan", messagetype="E")
        
        owner_data = owner_data[0]

        # Ambil data dasar store owner
        email = owner_data.get("email")
        full_name = owner_data.get("name_owner") or "Store Owner"
        store_name = owner_data.get("store_name") or "-"
        password = "securePassword123"   # HARDCODE, sesuaikan kalau pakai real
        login_url = "http://localhost:3000/Login"
        virtual_account = owner_data.get("no_virtual_account", "-")

        # Ambil data paket dari package_id
        package_id = owner_data.get("package_id")
        package_duration = "-"
        package_type = "-"
        package_price = "-"

        if package_id:
            package_data = get_data(
                table_name="tbl_packages",
                filters={"package_id": package_id}
            )
            if package_data:
                package = package_data[0]
                package_duration = f"{package.get('duration', '-') or '-'} Bulan"
                package_type = package.get("package_name", "-")
                package_price = package.get("price", "-")

        # Update status payment_status dan is_active
        update_data(
            table_name="tbl_store_owners",
            data={
                "payment_status": True,
                "is_active": True,
                "update_at": timezone.now()
            },
            filters={"store_id": store_id}
        )

        # Kirim email verifikasi akun
        context = {
            "full_name": full_name,
            "store_name": store_name,
            "email": email or "-",
            "password": password,
            "package_duration": package_duration,
            "package_type": package_type,
            "package_price": package_price,
            "login_url": login_url,
            "virtual_account": virtual_account
        }

        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'posvana_api', 'posvana_api', 'templates', 'email', 'email_store_verified.html')
        )
        email_body = render_email_template(template_path, context)

        send_email(
            to=email,
            subject="Akun Toko Anda Telah Diverifikasi!",
            message=email_body,
            content_type='text/html'
        )

        # Insert notifikasi
        insert_notification(
            user_id=store_id,
            target_role='store_owner',
            notif_type='payment_verified',
            title='Pembayaran Diverifikasi',
            message=f"Pembayaran untuk akun toko {store_name} berhasil diverifikasi. Akun Anda sekarang aktif.",
            data=json.dumps({
                "store_id": store_id,
                "status": "verified"
            })
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

@csrf_exempt
def list_package(request):
    try:
        with transaction.atomic():
            list_packages = get_data(table_name="tbl_packages")
            list_package_features = get_data(table_name="tbl_package_features")
            list_master_features = get_data(table_name="master_features")

            # Build feature lookup untuk master fitur
            feature_dict = {f["feature_id"]: f for f in list_master_features}

            result = []

            for package in list_packages:
                package_id = package["package_id"]

                active_feature_ids = [
                    pf["feature_id"] for pf in list_package_features if pf["package_id"] == package_id
                ]

                features = []
                for feature in list_master_features:
                    features.append({
                        "feature_id": feature["feature_id"],
                        "feature_name": feature["feature_name"],
                        "feature_description": feature["feature_description"],
                        "is_active": feature["feature_id"] in active_feature_ids
                    })

                # Append paket + fitur ke result
                result.append({
                    "package_id": package["package_id"],
                    "package_name": package["package_name"],
                    "duration": package["duration"],
                    "price": package["price"],
                    "description": package["description"],
                    "features": features
                })

            return Response.ok(data=result, message="List data telah tampil", messagetype="S")
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

            # Validasi field wajib
            required_fields = ["package_name", "duration", "price", "description", "features"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(
                        request,
                        message=f"Field '{field}' wajib diisi",
                        messagetype="E"
                    )

            now = timezone.now()

            data_to_insert = {
                "package_name": json_data["package_name"],
                "duration": json_data["duration"],
                "price": json_data["price"],
                "description": json_data["description"],
                "created_at": now,
                "update_at": now,
            }

            # Insert ke tbl_packages, ambil package_id yg di-generate
            package_id = insert_get_id_data(
                table_name="tbl_packages",
                data=data_to_insert,
                column_id="package_id"
            )

            # Insert fitur ke tbl_package_features
            features = json_data.get("features", [])
            for feature_id in features:
                # Ambil nama fitur (opsional, jika hanya butuh ID saja, langkah ini bisa dilewati)
                feature_data = get_data(
                    table_name="master_features",
                    filters={"feature_id": feature_id}
                )
                if not feature_data:
                    raise Exception(f"Feature dengan ID {feature_id} tidak ditemukan")

                insert_data(
                    table_name="tbl_package_features",
                    data={
                        "package_id": package_id,
                        "feature_id": feature_id,
                        "created_at": now
                    }
                )

            # Insert notifikasi ke admin (contoh)
            insert_notification(
                user_id=user_id,
                target_role='super_admin',
                notif_type='package_created',
                title='Paket Baru Ditambahkan',
                message=f"Paket '{json_data['package_name']}' berhasil ditambahkan dengan ID {package_id}.",
                data=json.dumps({"package_id": package_id})
            )

            return Response.ok(
                data={"package_id": package_id},
                message="Paket dan fitur berhasil ditambahkan",
                messagetype="S"
            )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@jwt_required
@csrf_exempt
def update_package(request, package_id):
    try:
        validate_method(request, "PUT")

        with transaction.atomic():
            json_data = json.loads(request.body)
            user_id = request.user.get("user_id")  # user yang update

            # Validasi field wajib
            required_fields = ["package_name", "duration", "price", "description", "features"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(
                        request,
                        message=f"Field '{field}' wajib diisi",
                        messagetype="E"
                    )

            # Pastikan package ada
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

            now = timezone.now()

            # Update tbl_packages
            update_data(
                table_name="tbl_packages",
                data={
                    "package_name": json_data["package_name"],
                    "duration": json_data["duration"],
                    "price": json_data["price"],
                    "description": json_data["description"],
                    "update_at": now
                },
                filters={"package_id": package_id}
            )

            # Hapus fitur lama
            delete_data(
                table_name="tbl_package_features",
                filters={"package_id": package_id}
            )

            # Insert fitur baru
            features = json_data["features"]
            for feature_id in features:
                # Validasi feature_id
                feature_data = get_data(
                    table_name="master_features",
                    filters={"feature_id": feature_id}
                )
                if not feature_data:
                    raise Exception(f"Feature dengan ID {feature_id} tidak ditemukan")

                insert_data(
                    table_name="tbl_package_features",
                    data={
                        "package_id": package_id,
                        "feature_id": feature_id,
                        "created_at": now
                    }
                )

            # Tambahkan notifikasi
            insert_notification(
                user_id=user_id,
                target_role='super_admin',
                notif_type='package_updated',
                title='Paket Diperbarui',
                message=f"Paket '{json_data['package_name']}' (ID: {package_id}) berhasil diperbarui.",
                data=json.dumps({"package_id": package_id})
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
        user_id = request.user.get("user_id")  # user yang menghapus

        with transaction.atomic():
            # Pastikan paket ada
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

            package_name = existing_package[0].get("package_name", "-")

            # Hapus fitur terkait
            delete_data(
                table_name="tbl_package_features",
                filters={"package_id": package_id}
            )

            # Hapus data di tbl_packages
            delete_data(
                table_name="tbl_packages",
                filters={"package_id": package_id}
            )

            # Tambahkan notifikasi ke admin (atau role lain)
            insert_notification(
                user_id=user_id,
                target_role='super_admin',
                notif_type='package_deleted',
                title='Paket Dihapus',
                message=f"Paket '{package_name}' (ID: {package_id}) telah dihapus.",
                data=json.dumps({"package_id": package_id})
            )

            return Response.ok(
                data=package_id,
                message=f"Delete data dengan ID {package_id} berhasil",
                messagetype="S"
            )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def list_master_features(request):
    try:
        with transaction.atomic():
            
            List_Paket = get_data(
                table_name="master_features",
            )

            return Response.ok(data=List_Paket, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@jwt_required
@csrf_exempt
def detail_pengguna_paket(request):
    try:
        with transaction.atomic():

            package_id = request.GET.get("package_id")

            if not package_id:
                return Response.badRequest(request, message="Parameter 'package_id' wajib diisi", messagetype="E")

            detail_pengguna_paket = execute_query(
                """
                    SELECT * FROM public.view_users_per_package WHERE package_id = %s;
                """,
                params=(package_id,)
            )
            
            return Response.ok(data=detail_pengguna_paket, message="List data telah tampil", messagetype="S")
    
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
    

# NOTIFIKASI
@jwt_required
@csrf_exempt
def get_notifications(request):
    try:
        user = request.user
        if not user:
            return Response.badRequest(request, message="User tidak ditemukan", messagetype="E")

        user_id = user.get("user_id")
        role = user.get("role_name")
        print("user role:", role)

        search = request.GET.get("search")
        search_param = f"%{search}%" if search else None

        params = []

        # Super admin: ambil semua notifikasi
        if role == "SuperAdmin":
            base_query = "SELECT * FROM public.notifications"
        else:
            base_query = """
                SELECT *
                FROM public.notifications
                WHERE
            """
            if user_id:
                base_query += "(user_id = %s OR (user_id IS NULL AND target_role = %s))"
                params.extend([user_id, role])
            else:
                base_query += "(user_id IS NULL AND target_role = %s)"
                params.append(role)

        # Tambah filter search jika ada
        if search_param:
            if "WHERE" in base_query:
                base_query += " AND (title ILIKE %s OR message ILIKE %s)"
            else:
                base_query += " WHERE (title ILIKE %s OR message ILIKE %s)"
            params.extend([search_param, search_param])

        # Order by created_at desc
        base_query += " ORDER BY created_at DESC"

        notifications = execute_query(base_query, params=tuple(params))

        return Response.ok(
            data=notifications,
            message="Notifikasi berhasil diambil",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def mark_notification_read(request, notif_id):
    try:
        validate_method(request, "PATCH")

        update_data(
            table_name="notifications",
            data={"is_read": True},
            filters={"id": notif_id}
        )

        return Response.ok(
            message="Notifikasi berhasil ditandai sebagai sudah dibaca",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

    