# backend/caretakers/api_views.py

from django.http import Http404
from rest_framework import generics, permissions

from .models import Caretaker
from .serializers import CaretakerMeSerializer


class CaretakerMeView(generics.RetrieveAPIView):
    """GET /api/caretakers/me/ — the authenticated caretaker's own active
    property assignments. Feeds the caretaker dashboard."""

    serializer_class = CaretakerMeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        caretaker = getattr(self.request.user, "caretaker_profile", None)
        if caretaker is None:
            raise Http404
        return Caretaker.objects.get(pk=caretaker.pk)
