# backend/partners/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    Disbursement,
    DisbursementStatus,
    Investor,
    PayoutAccount,
    ReferralCommissionRule,
    Reseller,
    RevenueShareAgreement,
)


@admin.register(PayoutAccount)
class PayoutAccountAdmin(ModelAdmin):
    list_display = ("label", "phone_number", "is_active")
    search_fields = ("label", "phone_number")


@admin.register(Reseller)
class ResellerAdmin(ModelAdmin):
    list_display = ("full_name", "payout_account", "created_at")
    autocomplete_fields = ("user", "payout_account")
    search_fields = ("full_name",)


@admin.register(ReferralCommissionRule)
class ReferralCommissionRuleAdmin(ModelAdmin):
    list_display = ("reseller", "landlord", "rate_percent", "is_perpetual", "expires_at")
    autocomplete_fields = ("reseller", "landlord")


@admin.register(Investor)
class InvestorAdmin(ModelAdmin):
    list_display = ("full_name", "payout_account", "created_at")
    autocomplete_fields = ("user", "payout_account")
    search_fields = ("full_name",)


@admin.register(RevenueShareAgreement)
class RevenueShareAgreementAdmin(ModelAdmin):
    list_display = ("investor", "organization", "basis", "rate_percent", "payout_cadence")
    list_filter = ("basis", "payout_cadence")
    autocomplete_fields = ("investor", "organization")


@admin.register(Disbursement)
class DisbursementAdmin(ModelAdmin):
    list_display = ("recipient_type", "reseller", "investor", "amount", "status", "created_at")
    list_filter = ("recipient_type", "status")
    autocomplete_fields = ("reseller", "investor")
    actions = ["retry_failed_disbursement"]

    @admin.action(description="Retry failed disbursement (re-attempt B2C send)")
    def retry_failed_disbursement(self, request, queryset):
        from integrations.daraja import DarajaClient

        from .tasks import _send_disbursement

        client = DarajaClient.for_platform()
        retried = 0
        for disbursement in queryset.filter(status=DisbursementStatus.FAILED):
            recipient = disbursement.reseller or disbursement.investor
            phone_number = recipient.payout_account.phone_number if recipient else ""
            if not phone_number:
                continue
            _send_disbursement(client, disbursement, phone_number, remarks="Retry payout")
            retried += 1
        self.message_user(request, f"Retried {retried} disbursement(s).")