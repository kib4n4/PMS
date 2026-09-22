# backend/caretakers/urls.py

from django.urls import path

from .api_views import CaretakerMeView

urlpatterns = [
    path("caretakers/me/", CaretakerMeView.as_view(), name="caretaker-me"),
]
