import requests
from django.conf import settings

FONNTE_API_URL = "https://api.fonnte.com/send"

def send_order_receipt_via_whatsapp(order, customer_phone):
    """
    order: instance order, yang punya data nota, tanggal, detail pesanan dll.
    customer_phone: nomor hp customer, format 08xxxxxxxx
    """
    message = f"""
🌿 Leha Leha Laundry
🏠 PURI AGUNG RESIDENCE BLOK D1/1
📦 WORKSHOP C3/8-9 SEI LANGKAI-SAGULUNG
📞 08117000709 / 0857 6028 3141

🧾 No. Nota: {order.invoice_number}

👤 Pelanggan: {order.customer_name}
------------------------------------------------
🧺 Rincian Pesanan:
{order.item_name} ({order.category})
{order.quantity} pcs x Rp {order.price_per_item:,} = Rp {order.total_price:,}
Catatan: {order.note or '-'}
------------------------------------------------
Subtotal   = Rp {order.subtotal:,}
Diskon     = - Rp {order.discount:,}
Total      = Rp {order.final_total:,}
------------------------------------------------
💰 Status pembayaran: {'Sudah bayar' if order.is_paid else 'Belum bayar'}

📅 Tanggal pesanan: {order.order_date.strftime('%d %b %Y %H:%M')}
⏰ Estimasi selesai: {order.estimated_finish.strftime('%d %b %Y %H:%M')}

🔗 Cek status & nota elektronik:
https://status.laundryposapp.com?id={order.tracking_id}

✨ Powered by Laundry POS App
"""

    headers = {
        'Authorization': settings.FONNTE_API_TOKEN
    }
    data = {
        'target': customer_phone,
        'message': message,
    }
    try:
        response = requests.post(FONNTE_API_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # log error atau kirim ke sentry
        print(f"Error kirim WA: {e}")
        return None
