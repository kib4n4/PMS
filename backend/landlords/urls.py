# backend/landlords/urls.py

from django.urls import path

from .api_views import AdminOverviewView

urlpatterns = [
    path("admin/overview/", AdminOverviewView.as_view(), name="admin-overview"),
]
