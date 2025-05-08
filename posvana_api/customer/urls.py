from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('profile_cust/', views.profile_cust, name='profile_cust'),
    path('update_profile_cust/', views.update_profile_cust, name='update_profile_cust'),
    path('data_toko/', views.data_toko, name='data_toko'),
    path('list_toko/', views.list_toko, name='list_toko'),
    path('log_pemesanan/', views.log_pemesanan, name='log_pemesanan'),
    path('insert_order/', views.insert_order, name='insert_order'),
    path('daftar_menu/', views.daftar_menu, name='daftar_menu'),
    path('detail_log/', views.detail_log, name='detail_log'),
]   