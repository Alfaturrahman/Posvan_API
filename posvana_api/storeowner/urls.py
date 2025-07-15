from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    # Kasir
    path('list_antrian/', views.list_antrian, name='list_antrian'),
    path('insert_order/', views.insert_order, name='insert_order'),
    path('update_order/', views.update_order, name='update_order'),
    path('update_order_status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    # Laporan Keuntungan
    path('laporan_keutungan_dashboard/', views.laporan_keutungan_dashboard, name='laporan_keutungan_dashboard'),
    path('laporan_keutungan/', views.laporan_keutungan, name='laporan_keutungan'),
    # Page Produk
    path('daftar_produk/', views.daftar_produk, name='daftar_produk'),
    path('summary_produk/', views.summary_produk, name='summary_produk'),
    path('insert_produk/', views.insert_produk, name='insert_produk'),
    path('update_status/', views.update_status, name='update_status'),
    path('update_stock/', views.update_stock, name='update_stock'),
    path('update_produk/<int:product_id>/', views.update_produk, name='update_produk'),
    path('delete_produk/<int:product_id>/', views.delete_produk, name='delete_produk'),
    path('check_product_stock/', views.check_product_stock, name='check_product_stock'),
    # Page Menu
    path('daftar_produk/', views.daftar_produk, name='daftar_produk'),
    path('daftar_menu/', views.daftar_menu, name='daftar_menu'),
    # Page Riwayat Pesanan
    path('riwayat_pesanan/', views.riwayat_pesanan, name='riwayat_pesanan'),
    path('riwayat_detail_pesanan/', views.riwayat_detail_pesanan, name='riwayat_detail_pesanan'),
    path('update_order_status_online/', views.update_order_status_online, name='update_order_status_online'),
    # Page Profile
    path('profile/<int:store_id>/', views.profile, name='profile'),
    path('update_profile/<int:store_id>/', views.update_profile, name='update_profile'),
    # Update Status Toko
    path('update_open_status/', views.update_open_status, name='update_open_status'),
    # Stok Basah
    path('list_stok_basah/', views.list_stok_basah, name='list_stok_basah'),
    path('insert_stok_basah/', views.insert_stok_basah, name='insert_stok_basah'),
    path('detail_stok_basah/', views.detail_stok_basah, name='detail_stok_basah'),
    path('update_stok_basah/', views.update_stok_basah, name='update_stok_basah'),
    path('delete_stok_basah/<int:stock_entry_id>/', views.delete_stok_basah, name='delete_stok_basah'),
    # Pengeluaran
    path('list_pengeluaran/', views.list_pengeluaran, name='list_pengeluaran'),
    path('data_edit_pengeluaran/', views.data_edit_pengeluaran, name='data_edit_pengeluaran'),
    path('insert_pengeluaran/', views.insert_pengeluaran, name='insert_pengeluaran'),
    path('update_pengeluaran/', views.update_pengeluaran, name='update_pengeluaran'),
    path('delete_pengeluaran/<int:other_expenses_id>/', views.delete_pengeluaran, name='delete_pengeluaran'),
    # Uang Keluar
    path('laporan_uang_keluar/', views.laporan_uang_keluar, name='laporan_uang_keluar'),
    path('detail_pengeluaran/', views.detail_pengeluaran, name='detail_pengeluaran'),

    # tripay
    path('tripay_callback/', views.tripay_callback, name='tripay_callback'),
    path('create_tripay_transaction/', views.create_tripay_transaction, name='create_tripay_transaction'),
    path('check_payment_status/', views.check_payment_status, name='check_payment_status'),

]