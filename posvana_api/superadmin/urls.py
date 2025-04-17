from django.urls import path
from . import views

urlpatterns = [
    path('show_store_owners/', views.show_store_owners, name='show_store_owners'),
    path('detail_store_owners/', views.detail_store_owners, name='detail_store_owners'),
    path('validate_store_owner/', views.validate_store_owner, name='validate_store_owner'),
    path('verify_payment/', views.verify_payment, name='verify_payment'),
]