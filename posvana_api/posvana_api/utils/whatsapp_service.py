# posvana_api/utils/whatsapp_service.py
import requests
from django.conf import settings
from common.transaction_helper import *


def format_currency(value):
    return f"Rp {int(value):,}".replace(",", ".")

def send_invoice(order_id):
    # Ambil data order
    orders = get_data("tbl_orders", filters={"order_id": order_id})
    if not orders:
        print(f"[WA Service] Order {order_id} not found")
        return

    order = orders[0]

    customer_name = order['customer_name']
    order_code = order['order_code']
    date = order['date']
    total_amount = order['total_amount']
    order_status = order['order_status']
    pickup_date = order.get('pickup_date')
    pickup_time = order.get('pickup_time')
    remarks = order.get('remarks') or '-'
    no_hp = order.get('no_hp') # Hardcode sementara, ganti dengan nomor WA kamu sendiri

    # Format tanggal & jam (pastikan sesuai format database, bisa pakai dateutil.parser.parse)
    pickup_date_str = pickup_date or '-'
    pickup_time_str = pickup_time or '-'

    # Misalnya ada tripay_reference sebagai link status
    status_link = f"https://status.laundryposapp.com?id={order.get('tripay_reference', '')}"

    # Buat template pesan
    message = f"""
🧺 *POSVANA APP*
Bida Asri 1, Jl. Raja Isa No.31 blok a2, Baloi Permai, Batam Kota, Batam City, Riau Islands
📞 085264099824

🧾 *No. Nota:* {order_code}
👤 *Pelanggan:* {customer_name}

---------------------------------------------------
Rincian pesanan:
Total: {format_currency(total_amount)}
Catatan: {remarks}

---------------------------------------------------
💰 *Status pembayaran:* {order_status}

📅 *Tanggal pesanan:* {date}
⏰ *Estimasi selesai:* {pickup_date_str} {pickup_time_str}

✨ Powered by POSVANA APP
"""

    # Kirim ke API Fonnte
    try:
        res = requests.post(
            "https://api.fonnte.com/send",
            data={
                "target": no_hp,
                "message": message,
            },
            headers={
                "Authorization": settings.FONNTE_TOKEN
            }
        )
        print(f"[WA Service] Sent invoice to {no_hp}, status: {res.status_code}, response: {res.text}")
    except Exception as e:
        print(f"[WA Service] Error sending invoice: {e}")
