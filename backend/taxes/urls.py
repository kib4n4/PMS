# backend/taxes/urls.py

from django.urls import path

from .api_views import RentalIncomeReturnListView

urlpatterns = [
    path("taxes/returns/", RentalIncomeReturnListView.as_view(), name="rental-income-returns"),
]
