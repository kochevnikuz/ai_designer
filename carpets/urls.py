from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/generate/', views.generate_design_api, name='generate_design_api'),
]