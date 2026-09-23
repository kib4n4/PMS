# backend/messaging/webhook_urls.py

from django.urls import path

from . import webhook_views

urlpatterns = [
    path("whatsapp/", webhook_views.whatsapp_webhook, name="whatsapp-webhook"),
    path("twilio/", webhook_views.twilio_webhook, name="twilio-webhook"),
]