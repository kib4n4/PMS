# backend/accounts/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, OTPRequestView, OTPVerifyView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("otp/request/", OTPRequestView.as_view(), name="auth-otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="auth-otp-verify"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
]
