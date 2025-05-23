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
from posvana_api.utils.export_pdf import *
import re
from django.http.multipartparser import MultiPartParser
from django.utils import timezone
from django.utils.timezone import localtime

#Dashboard (STORE OWNER)

@jwt_required
@csrf_exempt
def dashboard(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            today = datetime.datetime.today()
            year = int(request.GET.get("year", today.year))
            month = int(request.GET.get("month", today.month))
            day = int(request.GET.get("day", today.day))

            dashboard_monthly = execute_query(
                """
                    SELECT * FROM summary_dashboard_monthly(%s, %s, %s);
                """,
                params=(store_id, year, month)
            )
            dashboard_yearly = execute_query(
                """
                    SELECT * FROM public.summary_dashboard_yearly(%s, %s);
                """,
                params=(store_id, year)
            )
            dashboard_daily = execute_query(
                """
                    SELECT * FROM summary_dashboard_daily(%s, %s, %s);
                """,
                params=(day, month, year)
            )
            dashboard_presentase = execute_query(
                """
                    SELECT * 
                    FROM summary_dashboard_persentase
                    WHERE store_id = %s
                    AND bulan = DATE %s;
                """,
                params=(store_id, f"{year}-{month:02d}-01")
            )

            dashboard = {
                "dashboard_monthly": dashboard_monthly,
                "dashboard_yearly": dashboard_yearly,
                "dashboard_daily": dashboard_daily,
                "dashboard_presentase": dashboard_presentase,
            }

            return Response.ok(data=dashboard, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

#Kasir (STORE OWNER)

@jwt_required
@csrf_exempt
def list_antrian(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            list_antrian = execute_query(
                """
                    SELECT * FROM public.antrian_info_by_store(%s);
                """,
                params=(store_id,)  
            )
            filtered_antrian = [item for item in list_antrian if item.get("order_status") == "in_progress"]

            return Response.ok(data=filtered_antrian, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_order_status(request, order_id):
    try:
        validate_method(request, "PUT")
        json_data = json.loads(request.body)
        new_status = json_data.get("order_status")

        if not new_status:
            return Response.badRequest(request, message="Field 'order_status' wajib diisi", messagetype="E")

        updated = update_data(
            table_name="tbl_orders",
            data={"order_status": new_status},
            filters={"order_id": order_id}
        )

        if updated == 0:
            return Response.badRequest(request, message="Order tidak ditemukan atau tidak ada perubahan", messagetype="E")

        return Response.ok(message="Status order berhasil diperbarui", messagetype="S")

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

            json_data = json.loads(request.body)
            
            # Cek field wajib di orders
            required_fields = ["date", "total_amount", "order_status", "payment_method", "order_items"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(request, message=f"Field '{field}' wajib diisi", messagetype="E")
            
            now = localtime(timezone.now())  # ini akan beri waktu sesuai TIME_ZONE di settings.py

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


#Laporan Keuntungan (STORE OWNER)

@jwt_required
@csrf_exempt
def laporan_keutungan_dashboard(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            laporan_keutungan = execute_query(
                """
                    SELECT * FROM summary_laporan_keuntungan(%s);
                """,
                params=(store_id,)  
            )

            return Response.ok(data=laporan_keutungan, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def laporan_keutungan(request):
    try:
        store_id = request.GET.get("store_id")

        if not store_id:
            return JsonResponse({'status': 'error', 'message': 'store_id harus disertakan'}, status=400)

        export_pdf = request.GET.get("export_pdf")
        if export_pdf == 'true':
            # Ambil data laporan keuntungan
            laporan_keutungan = execute_query(
                "SELECT * FROM laporan_keuntungan(%s);",
                params=(store_id,)
            )
            return generate_laporan_keuntungan_pdf(laporan_keutungan)

        # Jika tidak ekspor, kembalikan data dalam format biasa (JSON)
        laporan_keutungan = execute_query(
            "SELECT * FROM laporan_keuntungan(%s);",
            params=(store_id,)
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Data laporan keutungan berhasil diambil',
            'data': laporan_keutungan
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

#Produk (STORE OWNER)

@jwt_required
@csrf_exempt
def daftar_produk(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")
            product_type = request.GET.get("product_type")
            search = request.GET.get("search")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            query = "SELECT * FROM public.view_product_list WHERE store_id = %s"
            params = [store_id]

            if product_type:
                query += " AND product_type = %s"
                params.append(product_type)

            if search:
                query += " AND LOWER(product_name) LIKE %s"
                params.append(f"%{search.lower()}%")

            daftar_produk = execute_query(query, params=tuple(params))

            return Response.ok(data=daftar_produk, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def insert_produk(request):
    try:
        validate_method(request, "POST")
        
        if request.method != 'POST' or not request.FILES:
            return Response.badRequest(request, message="Invalid request. Please send as multipart/form-data.", messagetype="E")

        product_name = request.POST.get("product_name")
        store_id = request.POST.get("store_id")
        stock = request.POST.get("stock")
        product_type = request.POST.get("product_type")  # makanan / minuman
        capital_price = request.POST.get("capital_price")
        selling_price = request.POST.get("selling_price")
        description = request.POST.get("description")
        is_active = request.POST.get("is_active")

        if not all([product_name, store_id, stock, product_type, capital_price, selling_price, description]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        if not request.FILES.get("product_picture"):
            return Response.badRequest(request, message="Product picture is required", messagetype="E")

        if is_active is None:
            return Response.badRequest(request, message="Keterangan (is_active) is required", messagetype="E")

        # Convert is_active to boolean
        is_active = True if is_active == 'true' else False

        # Generate product_code
        prefix = "MK" if product_type.lower() == "makanan" else "DR"
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT product_code FROM tbl_products 
                WHERE product_code LIKE %s 
                ORDER BY product_code DESC 
                LIMIT 1
            """, [prefix + "%"])
            last_code = cursor.fetchone()
        
        if last_code:
            last_number = int(last_code[0][2:])  # ambil angka setelah prefix
        else:
            last_number = 0

        next_number = last_number + 1
        product_code = f"{prefix}{next_number:03d}"

        # Upload gambar
        product_picture = request.FILES.get("product_picture")
        fs = FileSystemStorage()
        filename = fs.save(product_picture.name, product_picture)
        file_url = fs.url(filename)

        now = datetime.datetime.now()

        data_to_insert = {
            "product_code": product_code,
            "product_name": product_name,
            "store_id": store_id,
            "stock": stock,
            "product_type": product_type,
            "capital_price": capital_price,
            "selling_price": selling_price,
            "description": description,
            "product_picture": file_url,
            "created_at": now,
            "update_at": now,
            "is_active": is_active  
        }

        product_id = insert_get_id_data(
            table_name="tbl_products",
            data=data_to_insert,
            column_id="product_id"
        )

        return Response.ok(
            data={"product_id": product_id, "product_code": product_code, "product_picture_url": file_url},
            message="Produk berhasil ditambahkan",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_produk(request, product_id):
    try:
        validate_method(request, "PUT")
        if request.method != "PUT":
            return Response.badRequest(request, message="Invalid HTTP method, expected PUT", messagetype="E")

        if not product_id:
            return Response.badRequest(request, message="Product ID not found in the request", messagetype="E")

        content_type = request.META.get("CONTENT_TYPE", "")
        if "multipart/form-data" not in content_type:
            return Response.badRequest(request, message="Content-Type must be multipart/form-data", messagetype="E")

        parser = MultiPartParser(request.META, request, request.upload_handlers)
        parsed_data, parsed_files = parser.parse()

        product_code = parsed_data.get("product_code")
        product_name = parsed_data.get("product_name")
        store_id = parsed_data.get("store_id")
        stock = parsed_data.get("stock")
        product_type = parsed_data.get("product_type")
        capital_price = parsed_data.get("capital_price")
        selling_price = parsed_data.get("selling_price")
        description = parsed_data.get("description")
        raw_is_active = parsed_data.get("is_active")

        # Pastikan bahwa raw_is_active tidak None dan lakukan konversi
        if raw_is_active is None:
            return Response.badRequest(request, message="Keterangan (is_active) is required", messagetype="E")

        # Konversi dan cek apakah nilai raw_is_active adalah 'true'
        print("Raw is_active received:", raw_is_active)  # Ini akan memastikan bahwa nilai diterima dengan benar
        is_active = str(raw_is_active).strip().lower() == 'true'
        print("is_active value after conversion:", is_active)  # Ini akan memastikan bahwa nilai konversi benar


        if not all([product_code, product_name, store_id, stock, product_type, capital_price, selling_price, description]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        product_picture = parsed_files.get("product_picture")
        file_url = None

        if product_picture:
            fs = FileSystemStorage()
            filename = fs.save(product_picture.name, product_picture)
            file_url = fs.url(filename)
        else:
            # Ambil gambar lama berdasarkan product_id
            file_url = get_value(
                table_name="tbl_products",
                column_name="product_picture",
                filters={"product_id": product_id}
            )

            if not file_url:
                return Response.badRequest(request, message="Gambar lama tidak ditemukan", messagetype="E")

        now = datetime.datetime.now()

        if is_active is None:
            return Response.badRequest(request, message="Keterangan (is_active) is required", messagetype="E")

        # Siapkan data untuk diupdate
        data_to_update = {
            "product_code": product_code,
            "product_name": product_name,
            "store_id": store_id,
            "stock": stock,
            "product_type": product_type,
            "capital_price": capital_price,
            "selling_price": selling_price,
            "description": description,
            "product_picture": file_url,  # Bisa null jika tidak ada gambar baru
            "update_at": now,
            "is_active": is_active
        }

        print("DATA TO UPDATE:", data_to_update)

        # Melakukan update pada database
        update_data(
            table_name="tbl_products",
            data=data_to_update,
            filters={"product_id": product_id}
        )

        return Response.ok(
            data={"product_id": product_id, "product_picture_url": file_url},
            message="Produk berhasil diperbarui",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_status(request):
    try:
        # Pastikan metode adalah PUT
        if request.method != "PUT":
            return Response.badRequest(
                request, message="Invalid HTTP method, expected PUT", messagetype="E"
            )

        # Ambil parameter dari query string
        product_id = request.GET.get("product_id")
        is_active = request.GET.get("is_active")

        # Validasi product_id
        if not product_id:
            return Response.badRequest(
                request, message="Product ID is required", messagetype="E"
            )

        # Validasi is_active
        if is_active is None:
            return Response.badRequest(
                request, message="is_active is required", messagetype="E"
            )

        # Validasi dan konversi is_active ke boolean
        is_active_str = is_active.lower()
        if is_active_str not in ['true', 'false']:
            return Response.badRequest(
                request,
                message="Invalid value for is_active, must be 'true' or 'false'",
                messagetype="E"
            )
        is_active_bool = is_active_str == 'true'  # hasil akhir: True atau False

        # Update database
        now = datetime.datetime.now()
        update_data(
            table_name="tbl_products",
            data={
                "is_active": is_active_bool,  # Gunakan boolean True / False
                "update_at": now
            },
            filters={"product_id": int(product_id)}
        )

        return Response.ok(
            data={"product_id": product_id, "is_active": is_active_bool},
            message="Status produk berhasil diperbarui",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(
            request, message=str(e), messagetype="E"
        )

@jwt_required
@csrf_exempt
def delete_produk(request, product_id):
    try:
        with transaction.atomic():
            
            delete_data(
                table_name="tbl_products",
                filters={"product_id" : product_id }
            )

            return Response.ok(data=product_id, message=f"Delete data dengan ID {product_id} Berhasil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def summary_produk(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            summary_produk = execute_query(
                """
                    SELECT * FROM public.product_summary_by_store(%s);  
                """,
                params=(store_id,)  
            )

            return Response.ok(data=summary_produk, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

#Daftar Menu (STORE OWNER)

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
                    SELECT * FROM public.view_product_list 
                    WHERE store_id = %s AND is_active = true;
                """,
                params=(store_id,)
            )

            return Response.ok(data=daftar_menu, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

#Riwayat Pesanan (STORE OWNER)

@jwt_required
@csrf_exempt
def riwayat_pesanan(request):
    try:
        tanggal = request.GET.get("tanggal")
        status = request.GET.get("status")
        search = request.GET.get("search")

        # Ambil store_id dari JWT (pastikan token menyimpan info ini saat login)
        store_id = request.user.get("reference_id") if isinstance(request.user, dict) else getattr(request.user, "reference_id", None)

        print(store_id)
        if not store_id:
            return Response.badRequest(request, message="Store ID not found in token", messagetype="E")

        # Filter dasar
        filters_ditempat = {
            "is_dine_in": True,
            "is_pre_order": False,
            "store_id": store_id,
        }
        filters_online = {
            "is_dine_in": False,
            "is_pre_order": True,
            "store_id": store_id,
        }

        if tanggal:
            filters_ditempat["created_at"] = tanggal
            filters_online["created_at"] = tanggal

        if status:
            filters_ditempat["order_status"] = status
            filters_online["order_status"] = status

        riwayat_pesanan_ditempat = get_data(
            "tbl_orders",
            filters=filters_ditempat,
            search=search,
            search_columns=['order_status', 'order_code'],
            order_by="created_at DESC"
        )

        riwayat_pesanan_online = get_data(
            "tbl_orders",
            filters=filters_online,
            search=search,
            search_columns=['order_status', 'order_code'],
            order_by="created_at DESC"
        )

        riwayat_pesanan = {
            "riwayat_pesanan_ditempat": riwayat_pesanan_ditempat,
            "riwayat_pesanan_online": riwayat_pesanan_online,
        }

        return Response.ok(data=riwayat_pesanan, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

#Riwayat Detail Pesanan (STORE OWNER)

@jwt_required
@csrf_exempt
def riwayat_detail_pesanan(request):
    try:
        with transaction.atomic():
            order_id = request.GET.get("order_id")

            if not order_id:
                return Response.badRequest(request, message="order_id harus disertakan", messagetype="E")

            riwayat_detail_pesanan = execute_query(
                """
                    SELECT get_order_json(%s);
                """,
                params=(order_id,)  # <- ini beneran tuple
            )

            return Response.ok(data=riwayat_detail_pesanan, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@jwt_required
@csrf_exempt
def profile(request, store_id):
    try:
        with transaction.atomic():
            
            profile = first_data(
                table_name="tbl_store_owners",
                filters={"store_id" : store_id}
            )

            return Response.ok(data=profile, message="List data telah tampil", messagetype="S")
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_profile(request, store_id):
    try:
        if request.method != "POST":
            return Response.badRequest(request, message="Gunakan metode POST", messagetype="E")

        # Match dengan nama field di FormData frontend
        nama_toko = request.POST.get("store_name")
        email = request.POST.get("email")
        nik = request.POST.get("no_nik")
        whatsapp = request.POST.get("no_hp")
        alamat = request.POST.get("store_address")
        jam_buka = request.POST.get("open_time")
        jam_tutup = request.POST.get("close_time")
        deskripsi = request.POST.get("description")

        pernyataan = request.FILES.get("statement_letter")
        ktp = request.FILES.get("ktp_picture")
        izin_usaha = request.FILES.get("business_license")
        foto_toko = request.FILES.get("store_picture")

        fs = FileSystemStorage()
        file_urls = {}

        def save_file(file_obj, label):
            if file_obj:
                filename = fs.save(file_obj.name, file_obj)
                file_urls[label] = fs.url(filename)

        save_file(pernyataan, "statement_letter")
        save_file(ktp, "ktp_picture")
        save_file(izin_usaha, "business_license")
        save_file(foto_toko, "store_picture")

        data_to_update = {
            "store_name": nama_toko,
            "email": email,
            "no_nik": nik,
            "no_hp": whatsapp,
            "store_address": alamat,
            "open_time": jam_buka,
            "close_time": jam_tutup,
            "description": deskripsi,
            "update_at": datetime.datetime.now()
        }
        data_to_update.update(file_urls)

        with transaction.atomic():
            update_data(
                table_name="tbl_store_owners",
                data=data_to_update,
                filters={"store_id": store_id}
            )

        return Response.ok(data=data_to_update, message="Profil berhasil diperbarui", messagetype="S")

    except Exception as e:
        return Response.badRequest(request, message=str(e), messagetype="E")
    

@jwt_required
@csrf_exempt
def update_open_status(request):
    try:
        if request.method != "PUT":
            return Response.badRequest(
                request, message="Invalid HTTP method, expected PUT", messagetype="E"
            )

        store_id = request.GET.get("store_id")
        is_open = request.GET.get("is_open")

        if not store_id:
            return Response.badRequest(
                request, message="store_id is required", messagetype="E"
            )

        if is_open is None:
            return Response.badRequest(
                request, message="is_open is required", messagetype="E"
            )

        is_open_str = is_open.lower()
        if is_open_str not in ['true', 'false']:
            return Response.badRequest(
                request,
                message="Invalid value for is_open, must be 'true' or 'false'",
                messagetype="E"
            )

        is_open_bool = is_open_str == 'true'

        now = datetime.datetime.now()
        update_data(
            table_name="tbl_store_owners",
            data={
                "is_open": is_open_bool,
                "update_at": now
            },
            filters={"store_id": int(store_id)}
        )

        return Response.ok(
            data={"store_id": store_id, "is_open": is_open_bool},
            message="Status buka/tutup toko berhasil diperbarui",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(
            request, message=str(e), messagetype="E"
        )

