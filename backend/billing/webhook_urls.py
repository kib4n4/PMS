# backend/billing/webhook_urls.py

from django.urls import path

from . import webhook_views

urlpatterns = [
    path("mpesa/c2b/validation/", webhook_views.mpesa_c2b_validation, name="mpesa-c2b-validation"),
    path("mpesa/c2b/confirmation/", webhook_views.mpesa_c2b_confirmation, name="mpesa-c2b-confirmation"),
    path("mpesa/stk/callback/", webhook_views.mpesa_stk_callback, name="mpesa-stk-callback"),
    path("mpesa/b2c/result/", webhook_views.mpesa_b2c_result, name="mpesa-b2c-result"),
    path("mpesa/b2c/timeout/", webhook_views.mpesa_b2c_timeout, name="mpesa-b2c-timeout"),
    path(
        "mpesa/transactionstatus/result/",
        webhook_views.mpesa_transaction_status_result,
        name="mpesa-transactionstatus-result",
    ),
    path(
        "mpesa/transactionstatus/timeout/",
        webhook_views.mpesa_transaction_status_timeout,
        name="mpesa-transactionstatus-timeout",
    ),
]
