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
from django.http.multipartparser import MultiPartParser



#Dashboard (STORE OWNER)

@jwt_required
@csrf_exempt
def dashboard(request):
    try:
        validate_method(request, "GET")
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            today = datetime.today()
            year = int(request.GET.get("year", today.year))
            month = int(request.GET.get("month", today.month))
            day = int(request.GET.get("day", today.day))

            dashboard_monthly = execute_query(
                """
                    SELECT * FROM summary_dashboard_monthly(%s);
                """,
                params=(store_id,)
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

#Laporan Keuntungan (STORE OWNER)

@jwt_required
@csrf_exempt
def laporan_keutungan(request):
    try:
        validate_method(request, "GET")
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

#Produk (STORE OWNER)

@jwt_required
@csrf_exempt
def daftar_produk(request):
    try:
        validate_method(request, "GET")
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

        product_code = request.POST.get("product_code")
        product_name = request.POST.get("product_name")
        store_id = request.POST.get("store_id")
        stock = request.POST.get("stock")
        product_type = request.POST.get("product_type")
        capital_price = request.POST.get("capital_price")
        selling_price = request.POST.get("selling_price")
        description = request.POST.get("description")

        if not all([product_code, product_name, store_id, stock, product_type, capital_price, selling_price, description]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        product_picture = request.FILES.get("product_picture")
        if not product_picture:
            return Response.badRequest(request, message="Product picture is required", messagetype="E")

        fs = FileSystemStorage()
        filename = fs.save(product_picture.name, product_picture)  # simpan file gambar
        file_url = fs.url(filename)  # URL gambar yang disimpan

        now = datetime.now()

        data_to_insert = {
            "product_code": product_code,
            "product_name": product_name,
            "store_id": store_id,
            "stock": stock,
            "product_type": product_type,
            "capital_price": capital_price,
            "selling_price": selling_price,
            "description": description,
            "product_picture": file_url,  # Menggunakan URL gambar yang sudah di-upload
            "created_at": now,
            "update_at": now
        }

        product_id = insert_get_id_data(
            table_name="tbl_products",
            data=data_to_insert,
            column_id="product_id"
        )

        return Response.ok(data={"product_id": product_id, "product_picture_url": file_url}, message="Produk berhasil ditambahkan", messagetype="S")

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

        if not all([product_code, product_name, store_id, stock, product_type, capital_price, selling_price, description]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        product_picture = parsed_files.get("product_picture")
        file_url = None

        if product_picture:
            fs = FileSystemStorage()
            filename = fs.save(product_picture.name, product_picture)
            file_url = fs.url(filename)  # Simpan gambar baru dan dapatkan URL-nya

        now = datetime.now()

        data_to_update = {
            "product_code": product_code,
            "product_name": product_name,
            "store_id": store_id,
            "stock": stock,
            "product_type": product_type,
            "capital_price": capital_price,
            "selling_price": selling_price,
            "description": description,
            "product_picture": file_url,  
            "update_at": now
        }

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
def delete_produk(request, product_id):
    try:
        validate_method(request, "DELETE")
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
        validate_method(request, "GET")
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
        validate_method(request, "GET")
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

#Riwayat Pesanan (STORE OWNER)

@jwt_required
@csrf_exempt
def riwayat_pesanan(request):
    try:
        validate_method(request, "GET")

        tanggal = request.GET.get("tanggal")
        status = request.GET.get("status")
        search = request.GET.get("search")

        filters_ditempat = {"is_dine_in": True, "is_pre_order": False}
        filters_online = {"is_dine_in": False, "is_pre_order": True}

        if tanggal:
            filters_ditempat["created_at"] = tanggal
            filters_online["created_at"] = tanggal

        if status:
            filters_ditempat["order_status"] = status
            filters_online["order_status"] = status

        riwayat_pesanan_ditempat = get_data("tbl_orders", filters=filters_ditempat,search=search,search_columns=['order_status','order_code'])
        riwayat_pesanan_online = get_data("tbl_orders", filters=filters_online,search=search,search_columns=['order_status','order_code'])
        
        riwayat_pesanan_ditempat= paginate_data(request,riwayat_pesanan_ditempat)
        riwayat_pesanan_online= paginate_data(request,riwayat_pesanan_online)

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
        validate_method(request, "GET")
        with transaction.atomic():
            store_code = request.GET.get("store_code")

            if not store_code:
                return Response.badRequest(request, message="store_code harus disertakan", messagetype="E")

            riwayat_detail_pesanan = execute_query(
                """
                    SELECT get_order_json(%s);
                """,
                params=(store_code,)  # <- ini beneran tuple
            )

            return Response.ok(data=riwayat_detail_pesanan, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
