"""Portal URL routing."""

from django.urls import path
from portal import views

urlpatterns = [
    path('', lambda r: __import__('django.shortcuts', fromlist=['redirect']).redirect('/dashboard/')),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('invoices/', views.invoices_view, name='invoices'),
    path('invoices/export/', views.export_invoices_csv, name='export_invoices'),
    path('invoices/<str:invoice_no>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoices/<str:invoice_no>/attachments/<str:file_name>/', views.download_attachment_view, name='download_attachment'),
    path('metrics/', views.metrics_view, name='metrics'),
    path('capacity/', views.capacity_view, name='capacity'),
]
