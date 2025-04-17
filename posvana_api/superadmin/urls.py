from django.urls import path
from . import views

urlpatterns = [
    # Page Pengajuan Toko
    path('show_store_owners/', views.show_store_owners, name='show_store_owners'),
    path('detail_store_owners/', views.detail_store_owners, name='detail_store_owners'),
    path('validate_store_owner/', views.validate_store_owner, name='validate_store_owner'),
    path('verify_payment/', views.verify_payment, name='verify_payment'),
    path('dashboard_pengajuan/', views.dashboard_pengajuan, name='dashboard_pengajuan'),
    # Page Daftar Paket 
    path('list_package/', views.list_package, name='list_package'),
    path('insert_package/', views.insert_package, name='insert_package'),
    path('update_package/<int:package_id>/', views.update_package, name='update_package'),
    path('delete_package/<int:package_id>/', views.delete_package, name='delete_package'),
    # Page Dashboard
    path('dashboard_data_store/', views.dashboard_data_store, name='dashboard_data_store'),
]