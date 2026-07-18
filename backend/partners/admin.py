# backend/partners/admin.py

from django.contrib import admin

from .models import (
    Disbursement,
    Investor,
    PayoutAccount,
    ReferralCommissionRule,
    Reseller,
    RevenueShareAgreement,
)


@admin.register(PayoutAccount)
class PayoutAccountAdmin(admin.ModelAdmin):
    list_display = ("label", "phone_number", "is_active")


@admin.register(Reseller)
class ResellerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "payout_account", "created_at")


@admin.register(ReferralCommissionRule)
class ReferralCommissionRuleAdmin(admin.ModelAdmin):
    list_display = ("reseller", "landlord", "rate_percent", "is_perpetual", "expires_at")


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "payout_account", "created_at")


@admin.register(RevenueShareAgreement)
class RevenueShareAgreementAdmin(admin.ModelAdmin):
    list_display = ("investor", "organization", "basis", "rate_percent", "payout_cadence")
    list_filter = ("basis", "payout_cadence")


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = ("recipient_type", "reseller", "investor", "amount", "status", "created_at")
    list_filter = ("recipient_type", "status")