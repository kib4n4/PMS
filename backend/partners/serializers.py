# backend/partners/serializers.py

"""
JSON serializers for the partners app's first-ever HTTP surface (see
partners/api_views.py, partners/urls.py) — previously this app was
Celery-task/admin-only with zero endpoints.
"""

from rest_framework import serializers

from landlords.models import Landlord

from .models import Disbursement, Investor, ReferralCommissionRule, Reseller, RevenueShareAgreement


class ReferredLandlordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Landlord
        fields = ["id", "full_name", "created_at"]
        read_only_fields = fields


class ReferralCommissionRuleSerializer(serializers.ModelSerializer):
    landlord_name = serializers.CharField(source="landlord.full_name", read_only=True)

    class Meta:
        model = ReferralCommissionRule
        fields = ["id", "landlord", "landlord_name", "basis", "rate_percent", "is_perpetual", "expires_at"]
        read_only_fields = fields


class DisbursementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disbursement
        fields = ["id", "recipient_type", "amount", "status", "mpesa_conversation_id", "created_at"]
        read_only_fields = fields


class ResellerDashboardSerializer(serializers.ModelSerializer):
    referred_landlords = ReferredLandlordSerializer(many=True, read_only=True)
    commission_rules = ReferralCommissionRuleSerializer(many=True, read_only=True)
    disbursements = DisbursementSerializer(many=True, read_only=True)

    class Meta:
        model = Reseller
        fields = ["id", "full_name", "referred_landlords", "commission_rules", "disbursements"]
        read_only_fields = fields


class RevenueShareAgreementSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)

    class Meta:
        model = RevenueShareAgreement
        fields = [
            "id", "organization", "organization_name", "basis", "rate_percent",
            "payout_cadence", "effective_start", "effective_end",
        ]
        read_only_fields = fields


class InvestorDashboardSerializer(serializers.ModelSerializer):
    agreements = RevenueShareAgreementSerializer(many=True, read_only=True)
    disbursements = DisbursementSerializer(many=True, read_only=True)

    class Meta:
        model = Investor
        fields = ["id", "full_name", "agreements", "disbursements"]
        read_only_fields = fields
