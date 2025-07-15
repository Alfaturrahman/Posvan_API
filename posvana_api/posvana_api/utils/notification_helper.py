from django.utils import timezone
from common.transaction_helper import insert_data
import pytz

def insert_notification(
    user_id=None,
    target_role=None,
    notif_type=None,
    title=None,
    message=None,
    data=None
):
    """
    Helper untuk insert notifikasi ke tabel notifications.
    
    - user_id: int (optional) → jika notifikasi ditujukan ke user tertentu
    - target_role: str (optional) → jika notifikasi ditujukan ke role ('customer', 'store_owner', 'super_admin')
    - notif_type: str (required) → tipe notifikasi (contoh: 'order', 'stock', 'info')
    - title: str (required) → judul notifikasi
    - message: str (optional) → isi pesan
    - data: dict (optional) → data tambahan, otomatis disimpan sebagai JSONB
    """

    if not notif_type or not title:
        raise ValueError("Field 'notif_type' dan 'title' wajib diisi")

    if not user_id and not target_role:
        raise ValueError("Harus diisi minimal 'user_id' atau 'target_role'")
    
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    now = timezone.now().astimezone(jakarta_tz).replace(tzinfo=None)  # Buat jadi naive datetime

    data_to_insert = {
        "user_id": user_id,
        "target_role": target_role,
        "type": notif_type,
        "title": title,
        "message": message,
        "data": data,
        "created_at": now,
        "is_read": False,
    }

    insert_data("notifications", data_to_insert)
