from django.urls import path
from . import views

urlpatterns = [
    # Page Produk
    path('daftar_produk/', views.daftar_produk, name='daftar_produk'),
    path('summary_produk/', views.summary_produk, name='summary_produk'),
    path('insert_produk/', views.insert_produk, name='insert_produk'),
    path('update_produk/<int:product_id>/', views.update_produk, name='update_produk'),
    path('delete_produk/<int:product_id>/', views.delete_produk, name='delete_produk'),
    
]