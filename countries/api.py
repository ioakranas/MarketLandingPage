"""GET /api/v1/countries: the countries a client may offer at registration."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from countries.models import Country
from countries.selectors import list_countries


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["iso_code", "name", "dial_code"]
        extra_kwargs = {
            "iso_code": {"help_text": "ISO 3166-1 alpha-2 code, e.g. GR."},
            "dial_code": {"help_text": "International dialling code without '+', e.g. 30."},
        }


@extend_schema_view(
    get=extend_schema(
        tags=["Countries"],
        operation_id="listCountries",
        summary="List the countries available at registration",
        description="Ordered by name. `iso_code` is what POST /api/v1/registrations expects "
        "as `country`, `dial_code` as `phone_code`.",
        responses=OpenApiResponse(CountrySerializer(many=True), "The selectable countries."),
    )
)
class CountryListView(ListAPIView):
    serializer_class = CountrySerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # public reference data: no session involved
    pagination_class = None  # a short, bounded reference list

    def get_queryset(self):
        return list_countries()
