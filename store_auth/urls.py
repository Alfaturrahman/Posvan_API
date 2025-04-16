from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_store_owner, name='register'),
]