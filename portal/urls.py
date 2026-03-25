"""Portal URL routing."""

from django.urls import path
from django.views.generic import RedirectView

from portal import views


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard'), name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('platform-overview/', views.platform_overview_view, name='platform_overview'),
    path('invoices/', views.invoices_view, name='invoices'),
    path('invoices/export/', views.export_invoices_csv, name='export_invoices'),
    path('invoices/<str:invoice_no>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoices/<str:invoice_no>/attachments/<str:file_name>/', views.download_attachment_view, name='download_attachment'),
    path('profit-loss/', views.profit_loss_view, name='profit_loss'),
    path('metrics/', views.metrics_view, name='metrics'),
    path('capacity/', views.capacity_view, name='capacity'),
    path('trading-analytics/', views.trading_analytics_view, name='trading_analytics'),
]

