# backend/accounts/views.py

import logging
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import OTPRequest, User
from .serializers import RoleTokenObtainPairSerializer, UserSerializer

_OTPRequestSerializer = inline_serializer(
    "OTPRequest",
    {
        "phone_number": serializers.CharField(),
        "channel": serializers.ChoiceField(choices=["whatsapp", "email"], required=False),
    },
)
_OTPRequestResponseSerializer = inline_serializer(
    "OTPRequestResponse",
    {"detail": serializers.CharField(), "debug_code": serializers.CharField(required=False)},
)
_OTPVerifySerializer = inline_serializer(
    "OTPVerify", {"phone_number": serializers.CharField(), "code": serializers.CharField()}
)
_TokenPairSerializer = inline_serializer(
    "TokenPairWithUser",
    {"access": serializers.CharField(), "refresh": serializers.CharField(), "user": UserSerializer()},
)
_LogoutRequestSerializer = inline_serializer("LogoutRequest", {"refresh": serializers.CharField()})

logger = logging.getLogger(__name__)

OTP_LIFETIME_MINUTES = 5
OTP_MAX_ATTEMPTS = 5


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/ {"username", "password"} — every User (any
    role) has a usable password via AbstractUser, so this isn't
    admin-only; it's the fallback path for any role, and the primary
    path for Dime staff. Phone-first roles normally use the OTP endpoints
    below instead.
    """

    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [AllowAny]


class OTPRequestView(APIView):
    """
    POST /api/auth/otp/request/ {"phone_number": "+2547...", "channel"?: "whatsapp"|"email"}
    Issues a 6-digit OTP for an EXISTING user only; this endpoint never
    creates accounts. Email delivery is real (Resend). WhatsApp OTP
    delivery needs a Meta-pre-approved message template — an external
    approval process, not a code gap — so it stays logged-only until one
    exists. In DEBUG, the code is also echoed in the response so login
    is testable end-to-end without a live channel.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Request an OTP",
        request=_OTPRequestSerializer,
        responses={200: _OTPRequestResponseSerializer},
        auth=[],
    )
    def post(self, request):
        phone_number = str(request.data.get("phone_number", "")).strip()
        channel = str(request.data.get("channel", "whatsapp")).strip().lower()
        if channel not in ("whatsapp", "email"):
            return Response({"detail": "channel must be 'whatsapp' or 'email'."}, status=status.HTTP_400_BAD_REQUEST)
        if not phone_number:
            return Response({"detail": "phone_number is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Always return the same generic response regardless of whether
        # the phone number is registered, so this endpoint can't be used
        # to enumerate accounts.
        code = None
        user = User.objects.filter(phone_number=phone_number).first()
        if user is not None:
            code = f"{random.randint(0, 999999):06d}"
            OTPRequest.objects.create(
                phone_number=phone_number,
                code_hash=make_password(code),
                channel=channel,
                expires_at=timezone.now() + timedelta(minutes=OTP_LIFETIME_MINUTES),
            )
            if channel == "email" and user.email:
                from messaging.tasks import send_email_notification

                send_email_notification.delay(
                    to_email=user.email,
                    subject="Your Dime PMS verification code",
                    html=f"<p>Your verification code is <strong>{code}</strong>. It expires in {OTP_LIFETIME_MINUTES} minutes.</p>",
                    related_object_type="OTPRequest",
                    related_object_id=phone_number,
                )
            else:
                logger.info(
                    "OTP issued for %s via %s (WhatsApp OTP delivery needs a Meta-approved template)",
                    phone_number, channel,
                )

        payload = {"detail": "If that phone number is registered, a code has been sent."}
        if settings.DEBUG and code:
            payload["debug_code"] = code
        return Response(payload)


class OTPVerifyView(APIView):
    """POST /api/auth/otp/verify/ {"phone_number", "code"} — issues a JWT pair."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify an OTP and receive a JWT pair",
        request=_OTPVerifySerializer,
        responses={200: _TokenPairSerializer},
        auth=[],
    )
    def post(self, request):
        phone_number = str(request.data.get("phone_number", "")).strip()
        code = str(request.data.get("code", "")).strip()
        if not phone_number or not code:
            return Response(
                {"detail": "phone_number and code are required."}, status=status.HTTP_400_BAD_REQUEST
            )

        invalid = Response({"detail": "Invalid or expired code."}, status=status.HTTP_400_BAD_REQUEST)

        otp = (
            OTPRequest.objects.filter(phone_number=phone_number, consumed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if not otp or otp.expires_at < timezone.now() or otp.attempt_count >= OTP_MAX_ATTEMPTS:
            return invalid

        if not check_password(code, otp.code_hash):
            otp.attempt_count += 1
            otp.save(update_fields=["attempt_count"])
            return invalid

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return invalid

        otp.consumed_at = timezone.now()
        otp.save(update_fields=["consumed_at"])
        user.is_phone_verified = True
        user.save(update_fields=["is_phone_verified"])

        refresh = RoleTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ {"refresh"} — blacklists the refresh token
    so it can't be replayed after logout."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Log out (blacklist refresh token)", request=_LogoutRequestSerializer, responses={205: None})
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """GET /api/auth/me/ — the frontend's source of truth for the logged-in user's role/profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Get the current user", responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data)
