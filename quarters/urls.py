from django.urls import path
from . import views

urlpatterns = [
    # --- Authentication & OTP Routes ---
    path('login/', views.request_otp_view, name='login'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('logout/', views.logout_view, name='logout'),

    # --- Role Portals ---
    path('', views.operator_submit_view, name='operator_submit'),
    path('success/', views.operator_success_view, name='operator_success'),
    path('supervisor/', views.supervisor_dashboard_view, name='supervisor_dashboard'),
    path('manager/', views.manager_overview_view, name='manager_overview'),

    # --- Actions & APIs ---
    path('api/verify-gps/<int:report_id>/', views.verify_gps_api, name='verify_gps_api'),
    path('supervisor/review/<int:report_id>/', views.review_inspection_view, name='review_inspection'),
    
]