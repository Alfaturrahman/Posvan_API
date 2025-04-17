from django.urls import path
from . import views

urlpatterns = [
    path('register-store/', views.register_store_owner, name='register-store'),
    path('register-customer/', views.register_customer, name='register-customer'),
    path('login_user/', views.login_user, name='login_user'),
]