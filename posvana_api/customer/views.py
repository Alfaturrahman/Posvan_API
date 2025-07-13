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
from posvana_api.utils.notification_helper import insert_notification

#PROFILE CUSTOMER

@jwt_required
@csrf_exempt
def profile_cust(request):
    try:
        # Mengambil customer_id dari request.user
        customer_id = request.user.get('reference_id')  # Mengambil user_id dari decoded token
        
        with transaction.atomic():
            profile_cust = first_data(
                table_name="tbl_customer",
                filters={"customer_id": customer_id},
            )

            if not profile_cust:
                return Response.badRequest(request, message="Customer not found", messagetype="E")

            return Response.ok(data=profile_cust, message="Profile customer berhasil ditampilkan", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@jwt_required
@csrf_exempt
def update_profile_cust(request):
    try:
        # Mendapatkan customer_id dari token yang telah di-decode
        customer_id = request.user.get('reference_id')  # Mengambil reference_id yang merupakan customer_id

        # Pastikan ada data yang dikirimkan dalam body atau form-data
        if not request.body and not request.POST:
            return Response.badRequest(request, message="No data provided", messagetype="E")

        # Menangani form-data yang dikirimkan
        data = request.POST
        avatar = request.FILES.get('avatar', None)  # Jika ada file avatar
        updated_fields = {}

        # Validasi input, misalnya hanya email, nama, dan phone_number yang ingin diupdate
        if 'email' in data:
            updated_fields['customer_email'] = data['email']
        if 'custname_name' in data:
            updated_fields['custname_name'] = data['custname_name']
        if 'phone_number' in data:
            updated_fields['phone_number'] = data['phone_number']

        # Jika tidak ada field yang valid untuk diupdate
        if not updated_fields:
            return Response.badRequest(request, message="No valid fields to update", messagetype="E")

        # Melakukan update data customer di database
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Menghasilkan klausa SET untuk query UPDATE
                set_clause = ', '.join([f"{key} = %s" for key in updated_fields.keys()])
                values = list(updated_fields.values())

                # Query untuk melakukan update
                query = f"""
                    UPDATE public.tbl_customer
                    SET {set_clause}
                    WHERE customer_id = %s
                """
                cursor.execute(query, values + [customer_id])  # Menambahkan customer_id ke query

            # Jika ada avatar, simpan file avatar
            if avatar:
                avatar_path = save_avatar(avatar)  # Ganti dengan fungsi penyimpanan file yang sesuai
                # Simpan path avatar ke tabel customer jika perlu
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE public.tbl_customer
                        SET avatar_path = %s
                        WHERE customer_id = %s
                    """, [avatar_path, customer_id])

            # --- Insert Notification setelah update berhasil ---
            insert_notification(
                user_id=customer_id,
                notif_type='info',
                title='Profil Berhasil Diperbarui',
                message='Profil kamu telah berhasil diperbarui.',
                data={"customer_id": customer_id}
            )

        return Response.ok(message="Profile updated successfully", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=f"Error during profile update: {str(e)}", messagetype="E")

def save_avatar(avatar):
    # Simpan avatar ke folder tertentu dan kembalikan path-nya
    file_path = f"avatars/{avatar.name}"
    with open(file_path, 'wb') as f:
        for chunk in avatar.chunks():
            f.write(chunk)
    return file_path


#Dashboard (STORE OWNER)

@jwt_required
@csrf_exempt
def data_toko(request):
    try:
        with transaction.atomic():
            user = request.user  
            email = request.user.get("email")

            data_toko = execute_query(
                """
                    SELECT * FROM tbl_store_owners;
                """,
            )

            return Response.ok(data=data_toko, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def list_toko(request):
    try:
        with transaction.atomic():

            list_toko = execute_query(
                """
                    SELECT * FROM view_store_summary ;
                """,
            )

            return Response.ok(data=list_toko, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def log_pemesanan(request):
    try:
        user = request.user
        user_id = user.get("user_id") if isinstance(user, dict) else getattr(user, "user_id", None)

        if not user_id:
            return Response.badRequest(request, message="User ID not found in token", messagetype="E")

        with transaction.atomic():
            log_pemesanan = execute_query(
                """
                SELECT * FROM view_order_summary
                WHERE role_id = 3 AND reference_id = %s
                ORDER BY created_at DESC;
                """,
                [user_id]
            )

            return Response.ok(data=log_pemesanan, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@jwt_required
@csrf_exempt
def insert_order(request):
    try:
        validate_method(request, "POST")
        with transaction.atomic():
            store_id = request.GET.get("store_id")
            user = request.user
            user_id = user.get("user_id")
            role = user.get("role")  # 'store_owner', 'customer', 'super_admin'

            json_data = json.loads(request.body)
            
            # Cek field wajib di orders
            required_fields = ["date", "total_amount", "order_status", "payment_method", "order_items"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(request, message=f"Field '{field}' wajib diisi", messagetype="E")
            
            now = timezone.now()

            # Generate order code
            order_code = generate_order_code()

            # Isi field opsional kalau tidak ada
            customer_name = json_data.get("customer_name", "")
            remarks = json_data.get("remarks", "")
            pickup_date = json_data.get("pickup_date", None)
            pickup_time = json_data.get("pickup_time", None)
            role_id = json_data.get("role_id", None)
            reference_id = json_data.get("reference_id", None)
            no_hp = json_data.get("no_hp", "")
            delivery_address = json_data.get("delivery_address", "")
            
            # Konversi boolean flag
            is_pre_order = json_data.get("is_pre_order", False)
            is_delivered = json_data.get("is_delivered", False)
            is_dine_in = json_data.get("is_dine_in", False)

            # Data untuk tbl_orders
            order_data = {
                "store_id": store_id,
                "customer_name": customer_name,
                "date": json_data["date"],
                "total_amount": json_data["total_amount"],
                "created_at": now,
                "is_pre_order": is_pre_order,
                "is_delivered": is_delivered,
                "is_dine_in": is_dine_in,
                "remarks": remarks,
                "pickup_date": pickup_date,
                "pickup_time": pickup_time,
                "role_id": role_id,
                "reference_id": reference_id,
                "no_hp": no_hp,
                "delivery_address": delivery_address,
                "order_code": order_code,
                "order_status": json_data["order_status"],
                "payment_method": json_data["payment_method"]
            }

            # Insert tbl_orders
            order_id = insert_get_id_data(
                table_name="tbl_orders",
                data=order_data,
                column_id="order_id"
            )

            # Insert ke tbl_order_items
            order_items = json_data["order_items"]
            if not order_items:
                return Response.badRequest(request, message="Order harus punya minimal 1 produk", messagetype="E")

            for item in order_items:
                item_required_fields = ["product_id", "selling_price", "product_type", "item"]
                for f in item_required_fields:
                    if f not in item:
                        return Response.badRequest(request, message=f"Field '{f}' di order_items wajib diisi", messagetype="E")

                # Periksa stok produk
                product_id = item["product_id"]
                quantity = item["item"]  # Anggap 'item' adalah jumlah pesanan
                stok_produk = get_data(
                    table_name="tbl_products",
                    filters={"product_id": product_id}
                )
                
                if stok_produk and stok_produk[0]['stock'] < quantity:
                    return Response.badRequest(request, message=f"Stok produk {stok_produk[0]['product_name']} tidak mencukupi", messagetype="E")

                # Kurangi stok produk
                new_stock = stok_produk[0]['stock'] - quantity
                update_data(
                    table_name="tbl_products",
                    data={"stock": new_stock},
                    filters={"product_id": product_id}
                )

                # Insert ke tbl_order_items
                item_data = {
                    "order_id": order_id,
                    "product_id": item["product_id"],
                    "selling_price": item["selling_price"],
                    "product_type": item["product_type"],
                    "item": item["item"],
                    "created_at": now
                }

                insert_data(
                    table_name="tbl_order_items",
                    data=item_data
                )

            # Notifikasi ke customer
            insert_notification(
                user_id=user_id,
                target_role='customer',
                notif_type='order',
                title='Pesanan Berhasil Dibuat',
                message=f"Pesanan kamu dengan kode {order_code} berhasil dibuat.",
                data=json.dumps({"order_id": order_id, "order_code": order_code, "store_id": store_id})
            )

            # Notifikasi ke store_owner
            insert_notification(
                user_id=store_id,
                target_role='store_owner',
                notif_type='order',
                title='Pesanan Baru',
                message=f"Ada pesanan baru dengan kode {order_code} yang masuk.",
                data=json.dumps({"order_id": order_id, "order_code": order_code, "store_id": store_id})
            )

        return Response.ok(data={"order_id": order_id, "order_code": order_code}, message="Pesanan berhasil ditambahkan", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

def generate_order_code():
    # Ambil jumlah order yang sudah ada
    latest_order = get_data(
        table_name="tbl_orders",
        filters={},
        order_by="-order_id",
        limit=1
    )
    if latest_order:
        last_code = latest_order[0]["order_code"]
        number = int(last_code[1:]) + 1
    else:
        number = 1

    return f"A{str(number).zfill(3)}"

@jwt_required
@csrf_exempt
def daftar_menu(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            daftar_menu = execute_query(
                """
                    SELECT * FROM public.view_product_list where store_id = %s;
                """,
                params=(store_id,)  
            )

            return Response.ok(data=daftar_menu, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def detail_log(request):
    try:
        with transaction.atomic():
            order_id = request.GET.get("order_id")

            if not order_id:
                return Response.badRequest(request, message="order_id harus disertakan", messagetype="E")

            detail_log = execute_query(
                """
                    SELECT get_order_json(%s);
                """,
                params=(order_id,) 
            )

            return Response.ok(data=detail_log, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")