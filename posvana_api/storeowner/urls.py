from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    # Kasir
    path('list_antrian/', views.list_antrian, name='list_antrian'),
    path('insert_order/', views.insert_order, name='insert_order'),
    path('update_order_status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    # Laporan Keuntungan
    path('laporan_keutungan_dashboard/', views.laporan_keutungan_dashboard, name='laporan_keutungan_dashboard'),
    path('laporan_keutungan/', views.laporan_keutungan, name='laporan_keutungan'),
    # Page Produk
    path('daftar_produk/', views.daftar_produk, name='daftar_produk'),
    path('summary_produk/', views.summary_produk, name='summary_produk'),
    path('insert_produk/', views.insert_produk, name='insert_produk'),
    path('update_status/', views.update_status, name='update_status'),
    path('update_produk/<int:product_id>/', views.update_produk, name='update_produk'),
    path('delete_produk/<int:product_id>/', views.delete_produk, name='delete_produk'),
    # Page Menu
    path('daftar_menu/', views.daftar_menu, name='daftar_menu'),
    # Page Riwayat Pesanan
    path('riwayat_pesanan/', views.riwayat_pesanan, name='riwayat_pesanan'),
    path('riwayat_detail_pesanan/', views.riwayat_detail_pesanan, name='riwayat_detail_pesanan'),
    # Page Profile
    path('profile/<int:store_id>/', views.profile, name='profile'),
    path('update_profile/<int:store_id>/', views.update_profile, name='update_profile'),
    # Update Status Toko
    path('update_open_status/', views.update_open_status, name='update_open_status'),
]