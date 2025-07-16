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
from posvana_api.utils.notification_helper import insert_notification
from posvana_api.utils.tripay_service import *
import time
from posvana_api.utils.tripay_service import create_transaction, create_signature
from posvana_api.utils.whatsapp_service import send_invoice



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
                params=(store_id, month, year)
            )
            dashboard_yearly = execute_query(
                """
                    SELECT * FROM summary_dashboard_yearly(%s, %s);
                """,
                params=(store_id, year)
            )
            # dashboard_daily = execute_query(
            #     """
            #         SELECT * FROM summary_dashboard_daily(%s, %s, %s, %s);
            #     """,
            #     params=(store_id, month, year, day)
            # )
            dashboard_daily = execute_query(
                """
                    SELECT * FROM summary_dashboard_daily(%s, %s, %s);
                """,
                params=(store_id, month, year)
            )

            dashboard_presentase = execute_query(
                """
                    SELECT * 
                    FROM summary_dashboard_persentase_harian
                    WHERE store_id = %s
                    AND tanggal = DATE %s;
                """,
                params=(store_id, f"{year}-{month:02d}-{day:02d}")
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
        user_id = request.user.get("user_id")

        if not new_status:
            return Response.badRequest(request, message="Field 'order_status' wajib diisi", messagetype="E")

        updated = update_data(
            table_name="tbl_orders",
            data={"order_status": new_status},
            filters={"order_id": order_id}
        )

        if updated == 0:
            return Response.badRequest(request, message="Order tidak ditemukan atau tidak ada perubahan", messagetype="E")
        # Setelah update status order berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='order_status_changed',
            title='Status Pesanan Berubah',
            message=f"Status pesanan ID {order_id} kini menjadi '{new_status}'.",
            data=json.dumps({"order_id": order_id, "new_status": new_status})
        )

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

            # ✅ Cek field wajib
            required_fields = ["date", "total_amount", "payment_method", "order_items"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(request, message=f"Field '{field}' wajib diisi", messagetype="E")

            order_items = json_data["order_items"]
            if not order_items:
                return Response.badRequest(request, message="Order harus punya minimal 1 produk", messagetype="E")

            now = localtime(timezone.now())
            order_code = generate_order_code()

            payment_method = json_data["payment_method"]

            # normalisasi: huruf kecil + spasi jadi underscore
            payment_method_normalized = payment_method.lower().replace(" ", "_")

            # valid payment methods
            valid_payment_methods = ["cash", "qris", "bayar_nanti"]
            if payment_method_normalized not in valid_payment_methods:
                return Response.badRequest(request, message="Payment method tidak valid", messagetype="E")

            # set order_status sesuai payment_method
            if payment_method_normalized == "cash":
                order_status = "in_progress"
            elif payment_method_normalized == "qris":
                order_status = "PENDING"
            elif payment_method_normalized == "bayar_nanti":
                order_status = "in_progress"
            else:
                order_status = "UNKNOWN"

            # ✅ Field opsional
            customer_name = json_data.get("customer_name", "")
            remarks = json_data.get("remarks", "")
            pickup_date = json_data.get("pickup_date")
            pickup_time = json_data.get("pickup_time")
            role_id = json_data.get("role_id")
            reference_id = json_data.get("reference_id")
            no_hp = json_data.get("no_hp", "")
            delivery_address = json_data.get("delivery_address", "")
            is_pre_order = json_data.get("is_pre_order", False)
            is_delivered = json_data.get("is_delivered", False)
            is_dine_in = json_data.get("is_dine_in", False)

            # ✅ Insert tbl_orders
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
                "order_status": order_status,
                "payment_method": json_data["payment_method"]
            }

            order_id = insert_get_id_data(
                table_name="tbl_orders",
                data=order_data,
                column_id="order_id"
            )

            # ✅ Insert tbl_order_items & cek stok
            for item in order_items:
                item_required_fields = ["product_id", "selling_price", "product_type", "item"]
                for f in item_required_fields:
                    if f not in item:
                        return Response.badRequest(request, message=f"Field '{f}' di order_items wajib diisi", messagetype="E")

                product_id = item["product_id"]
                quantity = item["item"]

                stok_produk = get_data("tbl_products", filters={"product_id": product_id})
                if not stok_produk:
                    return Response.badRequest(request, message=f"Produk dengan id {product_id} tidak ditemukan", messagetype="E")

                if stok_produk[0]['stock'] < quantity:
                    return Response.badRequest(request, message=f"Stok produk {stok_produk[0]['product_name']} tidak mencukupi", messagetype="E")

                # Kurangi stok
                new_stock = stok_produk[0]['stock'] - quantity
                update_data("tbl_products", {"stock": new_stock}, {"product_id": product_id})

                insert_data("tbl_order_items", {
                    "order_id": order_id,
                    "product_id": product_id,
                    "selling_price": item["selling_price"],
                    "product_type": item["product_type"],
                    "item": quantity,
                    "created_at": now
                })

            # ✅ Insert notifikasi
            insert_notification(
                user_id=store_id,
                target_role='store_owner',
                notif_type='order_created',
                title='Pesanan Baru Ditambahkan',
                message=f"Pesanan baru berhasil ditambahkan dengan ID {order_id}.",
                data=json.dumps({"order_id": order_id})
            )

        # ✅ Return ke frontend
        return Response.ok(
            data={
                "order_id": order_id,
                "order_code": order_code,
                "total_amount": json_data["total_amount"]
            },
            message="Pesanan berhasil dibuat. Silakan lanjut ke pembayaran.",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def create_tripay_transaction(request):
    try:
        validate_method(request, "POST")
        json_data = json.loads(request.body)

        order_id = json_data.get("order_id")
        payment_method = json_data.get("payment_method")

        if not order_id or not payment_method:
            return Response.badRequest(request, message="order_id & payment_method wajib diisi", messagetype="E")

        # Ambil data order
        order = get_data("tbl_orders", filters={"order_id": order_id})
        if not order:
            return Response.badRequest(request, message="Order tidak ditemukan", messagetype="E")
        order = order[0]

        merchant_ref = order['order_code']
        amount = int(order['total_amount'])
        customer_name = order['customer_name'] or "Customer"
        customer_email = "customer@email.com"
        customer_phone = order['no_hp'] or "08123456789"
        expired_time = int(time.time()) + 86400

        payload = {
            "method": payment_method,
            "merchant_ref": merchant_ref,
            "amount": amount,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "order_items": [
                {
                    "name": f"Pesanan #{order_id}",
                    "price": amount,
                    "quantity": 1
                }
            ],
            "return_url": "https://yourwebsite.com/payment/success",
            "callback_url": "https://314e0f5fd62f.ngrok-free.app/api/storeowner/tripay_callback/",
            "expired_time": expired_time,
            "signature": create_signature(merchant_ref, amount)
        }

        # Buat transaksi ke Tripay
        tripay_response = create_transaction(payload)
        reference = tripay_response['reference']

        # Panggil detail transaksi supaya dapat qr_url
        tripay_detail = get_transaction_detail(reference)
        qr_url = tripay_detail.get('qr_url')

        # Simpan reference ke DB
        update_data(
            table_name="tbl_orders",
            data={"tripay_reference": reference},
            filters={"order_id": order_id}
        )

        return Response.ok(
            data={
                "reference": reference,
                "payment_url": tripay_response['checkout_url'],
                "qr_url": qr_url,
                "amount": tripay_response['amount'],
                "expired_at": tripay_response['expired_time'],
                "payment_method": tripay_response['payment_name']
            },
            message="Transaksi pembayaran berhasil dibuat",
            messagetype="S"
        )
    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@csrf_exempt
def tripay_callback(request):
    """
    Handles Tripay payment callback notifications.

    Verifies the callback signature, processes payment status,
    and updates the corresponding order and payment records in the database.
    """
    try:
        # Log the raw request body for debugging purposes
        print("Tripay callback raw body:", request.body.decode())
        json_data = json.loads(request.body)

        # Extract essential data from the Tripay callback
        reference = json_data.get("reference")
        status = json_data.get("status")  # e.g., "PAID", "UNPAID", "EXPIRED", "FAILED"
        amount = float(json_data.get("total_amount", 0))
        paid_at = json_data.get("paid_at")
        payment_method = json_data.get("payment_method")
        callback_signature = request.headers.get("X-Callback-Signature")
        raw_body = request.body

        # Basic validation for crucial callback data
        if not reference or not status or not callback_signature:
            print(f"Tripay callback: Missing reference, status, or signature. Data: {json_data}")
            return JsonResponse({"success": False, "message": "Invalid data received"}, status=400)

        # Import and verify the callback signature for security
        from posvana_api.utils.tripay_service import verify_callback_signature
        if not verify_callback_signature(raw_body, callback_signature):
            print(f"Tripay callback: Invalid signature for reference {reference}")
            return JsonResponse({"success": False, "message": "Invalid signature"}, status=400)

        # Fetch the order associated with the Tripay reference
        order_records = get_data("tbl_orders", filters={"tripay_reference": reference})
        if not order_records:
            print(f"Tripay callback: Order not found for tripay_reference {reference}")
            return JsonResponse({"success": False, "message": "Order not found"}, status=404)
        
        # Unpack the order data (assuming get_data returns a list of records)
        order_info = order_records[0]
        order_id = order_info['order_id']
        is_pre_order = order_info.get('is_pre_order', False)

        # Convert paid_at timestamp to datetime object
        paid_datetime = None
        if paid_at:
            try:
                paid_datetime = timezone.datetime.fromtimestamp(int(paid_at), tz=timezone.get_current_timezone())
            except Exception as e:
                print(f"Tripay callback: Error converting paid_at {paid_at}: {e}")
                # Keep paid_datetime as None if conversion fails

        # Check and update/insert payment record
        existing_payment = get_data("tbl_payments", filters={"tripay_reference": reference})
        if existing_payment:
            update_data(
                "tbl_payments",
                data={
                    "status": status,
                    "paid_at": paid_datetime,
                    "raw_callback": json.dumps(json_data)
                },
                filters={"tripay_reference": reference}
            )
            print(f"Tripay callback: Updated existing payment for reference {reference} to status {status}")
        else:
            insert_data(
                "tbl_payments",
                data={
                    "order_id": order_id,
                    "tripay_reference": reference,
                    "amount": amount,
                    "status": status,
                    "payment_method": payment_method,
                    "paid_at": paid_datetime,
                    "raw_callback": json.dumps(json_data),
                    "created_at": timezone.now()
                }
            )
            print(f"Tripay callback: Inserted new payment record for reference {reference} with status {status}")

        # Determine the new order status based on payment status and order type
        new_order_status = "pending" # Default status for all non-PAID or unmatched cases

        if status == "PAID":
            if is_pre_order:
                new_order_status = "pending"  # Customer pesan online, perlu disiapkan dulu
            else:
                new_order_status = "in_progress"  # Kasir input langsung, sudah di tempat, langsung proses

        # You might consider additional conditions for other Tripay statuses (e.g., "EXPIRED", "FAILED")
        # For example:
        # elif status in ["EXPIRED", "FAILED"]:
        #     new_order_status = "cancelled" # Or "failed_payment" etc.

        # Update the order status in the database
        update_data("tbl_orders", data={"order_status": new_order_status}, filters={"order_id": order_id})
        print(f"Tripay callback: Updated order {order_id} status to {new_order_status}")

        send_invoice(order_id)
        print(f"Tripay callback: Sent WhatsApp invoice for order {order_id}")

        return JsonResponse({"success": True}, status=200)

    except Exception as e:
        # Catch any unexpected errors, log them, and return a 500 response
        import traceback
        print("Tripay callback error:", traceback.format_exc())
        # Assuming log_exception is defined to log to a file/service
        log_exception(request, e)
        return JsonResponse({"success": False, "message": str(e)}, status=500)
    
@csrf_exempt
@jwt_required
def check_payment_status(request):
    try:
        order_id = request.GET.get('order_id')
        if not order_id:
            return Response.badRequest(request, message="order_id wajib diisi", messagetype="E")
        
        order = get_data("tbl_orders", filters={"order_id": order_id})
        if not order:
            return Response.badRequest(request, message="Order tidak ditemukan", messagetype="E")
        
        order = order[0]
        return Response.ok(
            data={"status": order["order_status"]}, 
            message="Berhasil ambil status order",
            messagetype="S"
        )
    except Exception as e:
        return Response.badRequest(request, message=str(e), messagetype="E")
    
@csrf_exempt
@jwt_required
def check_product_stock(request):
    try:
        store_id = request.GET.get('store_id')
        if not store_id:
            return Response.badRequest(request, message="store_id wajib diisi", messagetype="E")

        products = get_data("tbl_products", filters={"store_id": store_id})
        for product in products:
            stock = product['stock']
            last_status = product.get('last_stock_status', 'normal')

            if stock == 0 and last_status != 'empty':
                insert_notification(
                    user_id=store_id,
                    target_role='store_owner',
                    notif_type='stock_empty',
                    title='Stok Produk Habis',
                    message=f"Stok produk '{product['product_name']}' sudah habis.",
                    data=json.dumps({"product_id": product["product_id"]})
                )
                update_data("tbl_products", filters={"product_id": product["product_id"]}, data={"last_stock_status": "empty"})

            elif stock <= 10 and stock > 0 and last_status != 'low':
                insert_notification(
                    user_id=store_id,
                    target_role='store_owner',
                    notif_type='stock_low',
                    title='Stok Produk Menipis',
                    message=f"Stok produk '{product['product_name']}' tinggal {stock}.",
                    data=json.dumps({"product_id": product["product_id"], "remaining_stock": stock})
                )
                update_data("tbl_products", filters={"product_id": product["product_id"]}, data={"last_stock_status": "low"})

            elif stock > 10 and last_status != 'normal':
                # update status balik ke normal, tidak perlu notif
                update_data("tbl_products", filters={"product_id": product["product_id"]}, data={"last_stock_status": "normal"})

        return Response.ok(message="Berhasil cek stok & kirim notifikasi", messagetype="S")
    except Exception as e:
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_order(request):
    try:
        validate_method(request, "PUT")
        with transaction.atomic():
            order_id = request.GET.get("order_id")
            user_id = request.user.get("user_id")  

            if not order_id:
                return Response.badRequest(request, message="order_id harus disertakan", messagetype="E")

            json_data = json.loads(request.body)

            # Validasi fields wajib di tbl_orders
            required_fields = ["date", "total_amount", "order_status", "payment_method", "order_items"]
            for field in required_fields:
                if field not in json_data:
                    return Response.badRequest(request, message=f"Field '{field}' wajib diisi", messagetype="E")

            now = localtime(timezone.now())

            # Ambil data order lama untuk kembalikan stok produk
            old_items = get_data(
                table_name="tbl_order_items",
                filters={"order_id": order_id}
            )

            for old_item in old_items:
                product_id = old_item["product_id"]
                quantity = old_item["item"]

                # Tambahkan lagi stok yang pernah dikurangi
                stok_produk = get_data(
                    table_name="tbl_products",
                    filters={"product_id": product_id}
                )
                if stok_produk:
                    new_stock = stok_produk[0]['stock'] + quantity
                    update_data(
                        table_name="tbl_products",
                        data={"stock": new_stock},
                        filters={"product_id": product_id}
                    )

            # Hapus order_items lama
            delete_data(
                table_name="tbl_order_items",
                filters={"order_id": order_id}
            )

            # Update data tbl_orders
            update_fields = {
                "customer_name": json_data.get("customer_name", ""),
                "date": json_data["date"],
                "total_amount": json_data["total_amount"],
                "remarks": json_data.get("remarks", ""),
                "pickup_date": json_data.get("pickup_date", None),
                "pickup_time": json_data.get("pickup_time", None),
                "role_id": json_data.get("role_id", None),
                "reference_id": json_data.get("reference_id", None),
                "no_hp": json_data.get("no_hp", ""),
                "delivery_address": json_data.get("delivery_address", ""),
                "is_pre_order": json_data.get("is_pre_order", False),
                "is_delivered": json_data.get("is_delivered", False),
                "is_dine_in": json_data.get("is_dine_in", False),
                "order_status": json_data["order_status"],
                "payment_method": json_data["payment_method"],
                "updated_at": now
            }
            update_data(
                table_name="tbl_orders",
                data=update_fields,
                filters={"order_id": order_id}
            )

            # Insert ulang order_items baru
            order_items = json_data["order_items"]
            if not order_items:
                return Response.badRequest(request, message="Order harus punya minimal 1 produk", messagetype="E")

            for item in order_items:
                item_required_fields = ["product_id", "selling_price", "product_type", "item"]
                for f in item_required_fields:
                    if f not in item:
                        return Response.badRequest(request, message=f"Field '{f}' di order_items wajib diisi", messagetype="E")

                product_id = item["product_id"]
                quantity = item["item"]

                # Cek stok cukup
                stok_produk = get_data(
                    table_name="tbl_products",
                    filters={"product_id": product_id}
                ) 

                if not stok_produk:
                    return Response.badRequest(request, message=f"Produk dengan id {product_id} tidak ditemukan", messagetype="E")

                if stok_produk[0]['stock'] < quantity:
                    return Response.badRequest(request, message=f"Stok produk {stok_produk[0]['product_name']} tidak mencukupi", messagetype="E")
                # Kurangi stok
                new_stock = stok_produk[0]['stock'] - quantity
                update_data(
                    table_name="tbl_products",
                    data={"stock": new_stock},
                    filters={"product_id": product_id}
                )

                # Insert ke tbl_order_items
                item_data = {
                    "order_id": order_id,
                    "product_id": product_id,
                    "selling_price": item["selling_price"],
                    "product_type": item["product_type"],
                    "item": quantity,
                    "created_at": now
                }
                insert_data(
                    table_name="tbl_order_items",
                    data=item_data
                )

                # Setelah update order berhasil
                insert_notification(
                    user_id=user_id,
                    target_role='store_owner',
                    notif_type='order_updated',
                    title='Pesanan Diperbarui',
                    message=f"Pesanan dengan ID {order_id} telah diperbarui.",
                    data=json.dumps({"order_id": order_id})
                )

        return Response.ok(data={"order_id": order_id}, message="Pesanan berhasil diupdate", messagetype="S")

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
            
            query += " ORDER BY created_at ASC"

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
        
        user_id = request.user.get("user_id")
        product_name = request.POST.get("product_name")
        store_id = request.POST.get("store_id")
        stock = request.POST.get("stock")
        product_type = request.POST.get("product_type")  # makanan / minuman
        selling_type = request.POST.get("selling_type")  # harian / permanen
        capital_price = request.POST.get("capital_price")
        selling_price = request.POST.get("selling_price")
        description = request.POST.get("description")
        is_active = request.POST.get("is_active")

        if not all([product_name, store_id, stock, product_type, capital_price, selling_price, description, selling_type]):
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
            "selling_type": selling_type,   
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

        # Setelah insert produk berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='product_created',
            title='Produk Baru Ditambahkan',
            message=f"Produk baru '{product_name}' berhasil ditambahkan dengan ID {product_id}.",
            data=json.dumps({"product_id": product_id})
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

        user_id = request.user.get("user_id")
        product_code = parsed_data.get("product_code")
        product_name = parsed_data.get("product_name")
        store_id = parsed_data.get("store_id")
        stock = parsed_data.get("stock")
        product_type = parsed_data.get("product_type")
        selling_type = parsed_data.get("selling_type")
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


        if not all([product_code, product_name, store_id, stock, product_type, selling_type, capital_price, selling_price, description]):
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
            "selling_type": selling_type,  
            "capital_price": capital_price,
            "selling_price": selling_price,
            "description": description,
            "product_picture": file_url,  # Bisa null jika tidak ada gambar baru
            "update_at": now,
            "is_active": is_active
        }


        # Melakukan update pada database
        update_data(
            table_name="tbl_products",
            data=data_to_update,
            filters={"product_id": product_id}
        )

        # Setelah update produk berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='product_updated',
            title='Produk Diperbarui',
            message=f"Produk '{product_name}' dengan ID {product_id} telah diperbarui.",
            data=json.dumps({"product_id": product_id})
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
def update_stock(request):
    try:
        # Pastikan metode adalah PUT
        if request.method != "PUT":
            return Response.badRequest(
                request, message="Invalid HTTP method, expected PUT", messagetype="E"
            )

        # Ambil parameter
        product_id = request.GET.get("product_id")
        new_stock = request.GET.get("new_stock")

        # Validasi product_id
        if not product_id:
            return Response.badRequest(
                request, message="Product ID is required", messagetype="E"
            )

        # Validasi new_stock
        if new_stock is None:
            return Response.badRequest(
                request, message="new_stock is required", messagetype="E"
            )

        try:
            new_stock_int = int(new_stock)
            if new_stock_int < 0:
                return Response.badRequest(
                    request, message="new_stock must be >= 0", messagetype="E"
                )
        except ValueError:
            return Response.badRequest(
                request, message="new_stock must be an integer", messagetype="E"
            )

        # Update database
        now = datetime.datetime.now()
        update_data(
            table_name="tbl_products",
            data={
                "stock": new_stock_int,
                "update_at": now
            },
            filters={"product_id": int(product_id)}
        )

        return Response.ok(
            data={"product_id": product_id, "new_stock": new_stock_int},
            message="Stok produk berhasil diperbarui",
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
            user_id = request.user.get("user_id")
            
            delete_data(
                table_name="tbl_products",
                filters={"product_id" : product_id }
            )
            # Setelah delete produk berhasil
            insert_notification(
                user_id=user_id,
                target_role='store_owner',
                notif_type='product_deleted',
                title='Produk Dihapus',
                message=f"Produk dengan ID {product_id} telah dihapus.",
                data=json.dumps({"product_id": product_id})
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
                    SELECT * FROM public.view_product_topfavorit 
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
def update_order_status_online(request):
    try:
        if request.method != "PUT":
            return Response.badRequest(
                request, message="Invalid HTTP method, expected PUT", messagetype="E"
            )

        order_code = request.GET.get("order_code")
        new_status = request.GET.get("new_status")
        reason = request.GET.get("reason")  # opsional

        if not order_code:
            return Response.badRequest(
                request, message="order_code is required", messagetype="E"
            )

        allowed_status = ["Pending", "in_progress", "Completed", "canceled"]
        if not new_status:
            return Response.badRequest(
                request, message="new_status is required", messagetype="E"
            )
        if new_status not in allowed_status:
            return Response.badRequest(
                request,
                message=f"Invalid new_status. Allowed: {', '.join(allowed_status)}",
                messagetype="E"
            )

        if new_status == "canceled" and not reason:
            return Response.badRequest(
                request,
                message="reason is required when rejecting an order",
                messagetype="E"
            )

        now = datetime.datetime.now()

        update_payload = {
            "order_status": new_status,
            "updated_at": now
        }
        if new_status == "canceled":
            update_payload["remarks"] = reason  # gunakan kolom remarks

        update_data(
            table_name="tbl_orders",
            data=update_payload,
            filters={"order_code": order_code}
        )

        return Response.ok(
            data={"order_code": order_code, "new_status": new_status},
            message="Status pesanan berhasil diperbarui",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(
            request, message=str(e), messagetype="E"
        )
    
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
    
@jwt_required
@csrf_exempt
def uang_keluar(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            uang_keluar = get_data(
                    table_name="tbl_other_expenses",
                    filters={"store_id": store_id}
                )
            
            # list_antrian = execute_query(
            #     """
            #         SELECT * FROM public.antrian_info_by_store(%s);
            #     """,
            #     params=(store_id,)  
            # )

            return Response.ok(data=uang_keluar, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

# Pengeluaran - Stock Basah

@jwt_required
@csrf_exempt
def list_stok_basah(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            uang_keluar = execute_query(
                """
                    SELECT * FROM view_stock_entry_with_summary WHERE store_id = %s;
                """,
                params=(store_id,)  # <- ini beneran tuple
            )

            return Response.ok(data=uang_keluar, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def insert_stok_basah(request):
    try:
        validate_method(request, "POST")

        data = {}
        proof_of_payment = None
        proof_of_payment_base64 = None
        user_id = request.user.get("user_id")

        if request.content_type.startswith('application/json'):
            body = json.loads(request.body)
            data['date'] = body.get("date")
            data['place'] = body.get("place")
            data['officer'] = body.get("officer")
            data['store_id'] = body.get("store_id")
            data['items'] = body.get("items")
            proof_of_payment_url = body.get("proof_of_payment")  # URL string
            proof_of_payment_base64 = body.get("proof_of_payment_base64")  # optional base64 string
        else:
            data['date'] = request.POST.get("date")
            data['place'] = request.POST.get("place")
            data['officer'] = request.POST.get("officer")
            data['store_id'] = request.POST.get("store_id")
            data['items'] = request.POST.get("items")
            proof_of_payment = request.FILES.get("proof_of_payment")

        # Validasi field
        if not all([data['date'], data['place'], data['officer'], data['store_id'], data['items']]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        # Upload proof_of_payment
        if proof_of_payment:  # form-data upload file
            fs = FileSystemStorage()
            filename = fs.save(proof_of_payment.name, proof_of_payment)
            proof_of_payment_url = fs.url(filename)
        elif proof_of_payment_base64:  # base64 upload
            import base64
            from django.core.files.base import ContentFile
            format, imgstr = proof_of_payment_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"bukti_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            data_file = ContentFile(base64.b64decode(imgstr), name=file_name)
            fs = FileSystemStorage()
            filename = fs.save(file_name, data_file)
            proof_of_payment_url = fs.url(filename)
        elif proof_of_payment_url:  # link langsung
            pass  # sudah dapat URL dari JSON, langsung dipakai
        else:
            return Response.badRequest(request, message="proof_of_payment is required", messagetype="E")

        # Insert ke tbl_stock_entry
        now = datetime.datetime.now()
        stock_entry_id = insert_get_id_data(
            table_name="tbl_stock_entry",
            data={
                "date": data['date'],
                "place": data['place'],
                "officer": data['officer'],
                "store_id": data['store_id'],
                "proof_of_payment": proof_of_payment_url,
                "created_at": now
            },
            column_id="stock_entry_id"
        )

        # Insert items (parsing JSON string kalau form-data)
        if isinstance(data['items'], str):
            items = json.loads(data['items'])
        else:
            items = data['items']

        for item in items:
            insert_data(
                table_name="tbl_stock_items",
                data={
                    "stock_entry_id": stock_entry_id,
                    "item_name": item['item_name'],
                    "unit": item['unit'],
                    "unit_price": item['unit_price'],
                    "quantity": item['quantity'],
                    "sub_total": item['sub_total'],
                    "created_at": now
                }
            )
        
        # Setelah insert stok basah berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='wet_stock_created',
            title='Stok Basah Baru Ditambahkan',
            message=f"Stok basah baru berhasil ditambahkan dengan ID {stock_entry_id}.",
            data=json.dumps({"stock_entry_id": stock_entry_id})
        )

        return Response.ok(
            data={"stock_entry_id": stock_entry_id, "proof_of_payment_url": proof_of_payment_url},
            message="Stok basah berhasil ditambahkan",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def detail_stok_basah(request):
    try:
        stock_entry_id = request.GET.get("stock_entry_id")
        if not stock_entry_id:
            return Response.badRequest(
                request, message="stock_entry_id harus disertakan", messagetype="E"
            )

        # Ambil data stock_entry
        stock_entry = first_data(
            table_name="tbl_stock_entry",
            filters={"stock_entry_id": stock_entry_id},
        )

        if not stock_entry:
            return Response.badRequest(request, message="Data tidak ditemukan", messagetype="E")

        # Ambil data items
        items = get_data(
            table_name="tbl_stock_items",
            filters={"stock_entry_id": stock_entry_id}
        )

        # Tambahkan kategori ke setiap item
        for item in items:
            item["kategori"] = "Bahan Baku"

        # Gabungkan items ke stock_entry
        stock_entry["items"] = items

        data = {
            "stock_entry": stock_entry
        }

        return Response.ok(data=data, message="Detail stok basah berhasil diambil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_stok_basah(request):
    try:
        validate_method(request, "POST")
        now = datetime.datetime.now()
        user_id = request.user.get("user_id")

        data = {}
        proof_of_payment = None
        proof_of_payment_base64 = None
        proof_of_payment_url = None

        if request.content_type.startswith('application/json'):
            body = json.loads(request.body)
            data['stock_entry_id'] = body.get("stock_entry_id")
            data['date'] = body.get("date")
            data['place'] = body.get("place")
            data['officer'] = body.get("officer")
            data['store_id'] = body.get("store_id")
            data['items'] = body.get("items")
            proof_of_payment_url = body.get("proof_of_payment")  # URL string
            proof_of_payment_base64 = body.get("proof_of_payment_base64")  # optional base64
        elif request.content_type.startswith('multipart/form-data'):
            data['stock_entry_id'] = request.POST.get("stock_entry_id")
            data['date'] = request.POST.get("date")
            data['place'] = request.POST.get("place")
            data['officer'] = request.POST.get("officer")
            data['store_id'] = request.POST.get("store_id")
            data['items'] = request.POST.get("items")
            proof_of_payment = request.FILES.get("proof_of_payment")  # new file
            proof_of_payment_url = request.POST.get("proof_of_payment_url")  # old url
        else:
            return Response.badRequest(request, message="Unsupported content type", messagetype="E")

        # Validasi field wajib
        if not all([data['stock_entry_id'], data['date'], data['place'], data['officer'], data['store_id'], data['items']]):
            return Response.badRequest(request, message="Semua field wajib diisi", messagetype="E")

        # Proses proof_of_payment
        if proof_of_payment:  # form-data upload file
            fs = FileSystemStorage()
            filename = fs.save(proof_of_payment.name, proof_of_payment)
            proof_of_payment_url = fs.url(filename)
        elif proof_of_payment_base64:  # base64 upload
            import base64
            from django.core.files.base import ContentFile
            format, imgstr = proof_of_payment_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"bukti_update_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            data_file = ContentFile(base64.b64decode(imgstr), name=file_name)
            fs = FileSystemStorage()
            filename = fs.save(file_name, data_file)
            proof_of_payment_url = fs.url(filename)
        elif proof_of_payment_url:
            pass  # pakai url lama
        else:
            return Response.badRequest(request, message="proof_of_payment is required", messagetype="E")

        # Parse items
        if isinstance(data['items'], str):
            items = json.loads(data['items'])
        else:
            items = data['items']

        # Update tbl_stock_entry
        update_data(
            table_name="tbl_stock_entry",
            filters={"stock_entry_id": data['stock_entry_id']},
            data={
                "date": data['date'],
                "place": data['place'],
                "officer": data['officer'],
                "store_id": data['store_id'],
                "proof_of_payment": proof_of_payment_url,
                "created_at": now
            }
        )

        # Hapus items lama, insert baru
        delete_data(
            table_name="tbl_stock_items",
            filters={"stock_entry_id": data['stock_entry_id']}
        )

        for item in items:
            insert_data(
                table_name="tbl_stock_items",
                data={
                    "stock_entry_id": data['stock_entry_id'],
                    "item_name": item['item_name'],
                    "unit": item['unit'],
                    "unit_price": item['unit_price'],
                    "quantity": item['quantity'],
                    "sub_total": item['sub_total'],
                    "created_at": now
                }
            )
        # Setelah update stok basah berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='wet_stock_updated',
            title='Stok Basah Diperbarui',
            message=f"Stok basah dengan ID { data['stock_entry_id']} telah diperbarui.",
            data=json.dumps({"stock_entry_id":  data['stock_entry_id']})
        )

        return Response.ok(
            data={"stock_entry_id": data['stock_entry_id'], "proof_of_payment_url": proof_of_payment_url},
            message="Stok basah berhasil diupdate",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def delete_stok_basah(request, stock_entry_id):
    try:
        
        user_id = request.user.get("user_id")

        if not stock_entry_id:
            return Response.badRequest(request, message="stock_entry_id harus disertakan", messagetype="E")

        # Hapus detail items dulu
        delete_data(
            table_name="tbl_stock_items",
            filters={"stock_entry_id": stock_entry_id}
        )

        # Hapus entry utamanya
        delete_data(
            table_name="tbl_stock_entry",
            filters={"stock_entry_id": stock_entry_id}
        )
        # Setelah delete stok basah berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='wet_stock_deleted',
            title='Stok Basah Dihapus',
            message=f"Stok basah dengan ID {stock_entry_id} telah dihapus.",
            data=json.dumps({"stock_entry_id": stock_entry_id})
        )

        return Response.ok(message="Stok basah berhasil dihapus", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

# Pengeluaran - Pengeluaran lainnya 

@jwt_required
@csrf_exempt
def list_pengeluaran(request):
    try:
        with transaction.atomic():
            store_id = request.GET.get("store_id")

            if not store_id:
                return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

            list_pengeluaran = execute_query(
                """
                    SELECT * FROM tbl_other_expenses WHERE store_id = %s;
                """,
                params=(store_id,)  # <- ini beneran tuple
            )

            return Response.ok(data=list_pengeluaran, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def insert_pengeluaran(request):
    try:
        validate_method(request, "POST")
        now = datetime.datetime.now()
        user_id = request.user.get("user_id")

        data = {}
        proof_of_expenses = None
        proof_of_expenses_base64 = None
        proof_of_expenses_url = None

        if request.content_type.startswith('application/json'):
            body = json.loads(request.body)
            data['date'] = body.get("date")
            data['store_id'] = body.get("store_id")
            data['description'] = body.get("description")
            data['spending'] = body.get("spending")
            data['type_expenses'] = body.get("type_expenses")
            proof_of_expenses_url = body.get("proof_of_expenses")  # URL string
            proof_of_expenses_base64 = body.get("proof_of_expenses_base64")  # optional base64 string
        else:
            data['date'] = request.POST.get("date")
            data['store_id'] = request.POST.get("store_id")
            data['description'] = request.POST.get("description")
            data['spending'] = request.POST.get("spending")
            data['type_expenses'] = request.POST.get("type_expenses")
            proof_of_expenses = request.FILES.get("proof_of_expenses")

        # Validasi field wajib
        if not all([data['date'], data['store_id'], data['description'], data['spending'], data['type_expenses']]):
            return Response.badRequest(request, message="All fields are required", messagetype="E")

        # Proses upload proof_of_expenses
        if proof_of_expenses:  # file upload
            fs = FileSystemStorage()
            filename = fs.save(proof_of_expenses.name, proof_of_expenses)
            proof_of_expenses_url = fs.url(filename)
        elif proof_of_expenses_base64:  # base64 upload
            import base64
            from django.core.files.base import ContentFile
            format, imgstr = proof_of_expenses_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"bukti_pengeluaran_{now.strftime('%Y%m%d%H%M%S')}.{ext}"
            data_file = ContentFile(base64.b64decode(imgstr), name=file_name)
            fs = FileSystemStorage()
            filename = fs.save(file_name, data_file)
            proof_of_expenses_url = fs.url(filename)
        elif proof_of_expenses_url:
            pass  # sudah dapat URL dari JSON
        else:
            return Response.badRequest(request, message="proof_of_expenses is required", messagetype="E")

        # Insert ke tbl_other_expenses
        other_expenses_id = insert_get_id_data(
            table_name="tbl_other_expenses",
            data={
                "date": data['date'],
                "store_id": data['store_id'],
                "description": data['description'],
                "spending": data['spending'],
                "proof_of_expenses": proof_of_expenses_url,
                "type_expenses": data['type_expenses'],
                "created_at": now
            },
            column_id="other_expenses_id"
        )

        # Setelah insert pengeluaran berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='expense_created',
            title='Pengeluaran Baru Ditambahkan',
            message=f"Pengeluaran baru berhasil dicatat dengan ID {other_expenses_id}.",
            data=json.dumps({"other_expenses_id": other_expenses_id})
        )

        return Response.ok(
            data={"other_expenses_id": other_expenses_id, "proof_of_expenses_url": proof_of_expenses_url},
            message="Pengeluaran berhasil ditambahkan",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def update_pengeluaran(request):
    try:
        validate_method(request, "POST")
        now = datetime.datetime.now()
        user_id = request.user.get("user_id")

        data = {}
        proof_of_expenses = None
        proof_of_expenses_base64 = None
        proof_of_expenses_url = None

        if request.content_type.startswith('application/json'):
            body = json.loads(request.body)
            data['other_expenses_id'] = body.get("other_expenses_id")
            data['store_id'] = body.get("store_id")
            data['date'] = body.get("date")
            data['description'] = body.get("description")
            data['spending'] = body.get("spending")
            data['type_expenses'] = body.get("type_expenses")
            proof_of_expenses_url = body.get("proof_of_expenses")  # pakai url lama
            proof_of_expenses_base64 = body.get("proof_of_expenses_base64")  # optional base64
        elif request.content_type.startswith('multipart/form-data'):
            data['other_expenses_id'] = request.POST.get("other_expenses_id")
            data['store_id'] = request.POST.get("store_id")
            data['date'] = request.POST.get("date")
            data['description'] = request.POST.get("description")
            data['spending'] = request.POST.get("spending")
            data['type_expenses'] = request.POST.get("type_expenses")
            proof_of_expenses = request.FILES.get("proof_of_expenses")  # file baru
            proof_of_expenses_url = request.POST.get("proof_of_expenses_url")  # pakai url lama
        else:
            return Response.badRequest(request, message="Unsupported content type", messagetype="E")

        # Validasi
        if not all([data['other_expenses_id'], data['store_id'], data['date'], data['description'], data['spending'], data['type_expenses']]):
            return Response.badRequest(request, message="Semua field wajib diisi", messagetype="E")

        # Handle proof_of_expenses
        if proof_of_expenses:
            fs = FileSystemStorage()
            filename = fs.save(proof_of_expenses.name, proof_of_expenses)
            proof_of_expenses_url = fs.url(filename)
        elif proof_of_expenses_base64:
            import base64
            from django.core.files.base import ContentFile
            format, imgstr = proof_of_expenses_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f"bukti_update_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            data_file = ContentFile(base64.b64decode(imgstr), name=file_name)
            fs = FileSystemStorage()
            filename = fs.save(file_name, data_file)
            proof_of_expenses_url = fs.url(filename)
        elif proof_of_expenses_url:
            pass
        else:
            return Response.badRequest(request, message="proof_of_expenses is required", messagetype="E")

        # Update data
        update_data(
            table_name="tbl_other_expenses",
            filters={"other_expenses_id": data['other_expenses_id']},
            data={
                "store_id": data['store_id'],
                "date": data['date'],
                "description": data['description'],
                "spending": data['spending'],
                "type_expenses": data['type_expenses'],
                "proof_of_expenses": proof_of_expenses_url,
                "created_at": now
            }
        )
        # Setelah update pengeluaran berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='expense_updated',
            title='Pengeluaran Diperbarui',
            message=f"Pengeluaran dengan ID {data['other_expenses_id']} telah diperbarui.",
            data=json.dumps({"other_expenses_id": data['other_expenses_id']})
        )

        return Response.ok(
            data={"other_expenses_id": data['other_expenses_id'], "proof_of_expenses_url": proof_of_expenses_url},
            message="Pengeluaran berhasil diupdate",
            messagetype="S"
        )

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def delete_pengeluaran(request,other_expenses_id):
    try:
        
        if not other_expenses_id:
            return Response.badRequest(request, message="other_expenses_id harus disertakan", messagetype="E")
        user_id = request.user.get("user_id")

        # Hapus data
        delete_data(
            table_name="tbl_other_expenses",
            filters={"other_expenses_id": other_expenses_id}
        )

        # Setelah delete pengeluaran berhasil
        insert_notification(
            user_id=user_id,
            target_role='store_owner',
            notif_type='expense_deleted',
            title='Pengeluaran Dihapus',
            message=f"Pengeluaran dengan ID {other_expenses_id} telah dihapus.",
            data=json.dumps({"other_expenses_id": other_expenses_id})
        )

        return Response.ok(message="Pengeluaran berhasil dihapus", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def data_edit_pengeluaran(request):
    try:
        other_expenses_id = request.GET.get("other_expenses_id")
        if not other_expenses_id:
            return Response.badRequest(
                request, message="other_expenses_id harus disertakan", messagetype="E"
            )

        # Ambil data other_expenses
        other_expenses = first_data(
            table_name="tbl_other_expenses",
            filters={"other_expenses_id": other_expenses_id},
        )

        if not other_expenses:
            return Response.badRequest(request, message="Data tidak ditemukan", messagetype="E")

        return Response.ok(data=other_expenses, message="Detail pengeluaran berhasil diambil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

# Laporan - Uang Keluar

@jwt_required
@csrf_exempt
def laporan_uang_keluar(request):
    try:
        store_id = request.GET.get("store_id")

        if not store_id:
            return Response.badRequest(request, message="store_id harus disertakan", messagetype="E")

        export_pdf = request.GET.get("export_pdf")

        # Ambil data list pengeluaran
        list_pengeluaran = execute_query(
            """
            SELECT * FROM vw_pengeluaran_semua WHERE store_id = %s;
            """,
            params=(store_id,)
        )

        if export_pdf == 'true':
            # Panggil fungsi untuk generate PDF
            return generate_laporan_uang_keluar_pdf(list_pengeluaran)

        # Jika tidak ekspor, kembalikan data JSON
        return Response.ok(data=list_pengeluaran, message="List data telah tampil", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")

@jwt_required
@csrf_exempt
def detail_pengeluaran(request):
    try:
        with transaction.atomic():
            source = request.GET.get("source")
            id = request.GET.get("id")  # ini bisa stock_entry_id atau other_expenses_id

            if not source or not id:
                return Response.badRequest(
                    request,
                    message="Parameter source dan id harus disertakan",
                    messagetype="E",
                )

            data = None

            if source == "stock_entry":
                # Ambil detail stock_entry beserta itemnya
                data_header = execute_query(
                    """
                    SELECT stock_entry_id, date, place, officer, proof_of_payment, created_at, store_id
                    FROM tbl_stock_entry
                    WHERE stock_entry_id = %s
                    """,
                    params=(id,)
                )
                data_items = execute_query(
                    """
                    SELECT stock_item_id, item_name, unit, unit_price, quantity, sub_total, created_at
                    FROM tbl_stock_items
                    WHERE stock_entry_id = %s
                    """,
                    params=(id,)
                )
                if data_header:
                    data = {
                        "header": data_header[0],
                        "items": data_items
                    }
                else:
                    return Response.badRequest(
                        request,
                        message="Data stock_entry tidak ditemukan",
                        messagetype="E",
                    )

            elif source == "other_expenses":
                # Ambil detail other_expenses
                data_detail = execute_query(
                    """
                    SELECT other_expenses_id, date, description, spending, proof_of_expenses, type_expenses, created_at, store_id
                    FROM tbl_other_expenses
                    WHERE other_expenses_id = %s
                    """,
                    params=(id,)
                )
                if data_detail:
                    data = data_detail[0]
                else:
                    return Response.badRequest(
                        request,
                        message="Data other_expenses tidak ditemukan",
                        messagetype="E",
                    )

            else:
                return Response.badRequest(
                    request,
                    message="source harus bernilai 'stock_entry' atau 'other_expenses'",
                    messagetype="E",
                )

            return Response.ok(data=data, message="Detail pengeluaran berhasil ditampilkan", messagetype="S")

    except Exception as e:
        log_exception(request, e)
        return Response.badRequest(request, message=str(e), messagetype="E")
