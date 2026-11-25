"""GET /api/v1/countries: the countries a client may offer at registration."""

from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from countries.models import Country
from countries.selectors import list_countries


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["iso_code", "name", "dial_code"]


class CountryListView(ListAPIView):
    serializer_class = CountrySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # a short, bounded reference list

    def get_queryset(self):
        return list_countries()
