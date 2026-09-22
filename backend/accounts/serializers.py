# backend/accounts/serializers.py

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    is_super_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "phone_number",
            "role",
            "is_phone_verified",
            "is_super_admin",
            "first_name",
            "last_name",
        ]
        read_only_fields = fields


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Same as SimpleJWT's default username+password login, plus a `role`
    claim on the token itself (so the frontend's middleware can read role
    straight off the JWT for route-gating) and the user's profile in the
    response body (so it doesn't need a second round trip to /me/).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["is_super_admin"] = user.is_superuser
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
