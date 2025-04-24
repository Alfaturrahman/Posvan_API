from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('data_toko/', views.data_toko, name='data_toko'),
]