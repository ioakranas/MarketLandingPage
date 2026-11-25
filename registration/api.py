"""POST /api/v1/registrations: create a customer account."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.api import ApiProblem
from common.schema import CSRF_PROBLEM, RATE_LIMITED_PROBLEM, problem, validation_problem
from registration.serializers import CustomerResponseSerializer, RegistrationRequestSerializer
from registration.services import EmailAlreadyRegistered, register_customer


# DRF only checks CSRF for logged-in users. The API is called by our own pages with the
# session cookie, so anonymous POSTs (sign-up, login) are protected too: a third-party
# site must not be able to submit them in a visitor's browser.
@method_decorator(csrf_protect, name="dispatch")
class RegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # anonymous endpoint
    throttle_scope = "registrations"  # settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    @extend_schema(
        tags=["Registration"],
        operation_id="registerCustomer",
        summary="Register a customer",
        description="Creates the login identity and the customer profile in one transaction. "
        "The email is case-insensitive and must not be registered yet.",
        request=RegistrationRequestSerializer,
        examples=[
            OpenApiExample(
                "Valid registration",
                request_only=True,
                value={
                    "first_name": "Ioannis",
                    "last_name": "Papadopoulos",
                    "country": "GR",
                    "phone_code": "30",
                    "phone": "6912345678",
                    "email": "ioannis@example.com",
                    "password": "Secret#123",
                    "terms": True,
                },
            )
        ],
        responses=dict(
            [
                (201, OpenApiResponse(CustomerResponseSerializer, "Customer registered.")),
                validation_problem({"phone_code": "Country code does not match the selected country."}),
                CSRF_PROBLEM,
                problem(
                    409,
                    "email-already-registered",
                    "Email already registered",
                    "An account with this email already exists.",
                    "The email belongs to an existing account (compared case-insensitively).",
                    errors={"email": "This email is already registered. Please log in instead."},
                ),
                RATE_LIMITED_PROBLEM,
            ]
        ),
    )
    def post(self, request):
        serializer = RegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # -> 400 Problem Details

        try:
            customer = register_customer(serializer.validated_data)
        except EmailAlreadyRegistered:
            raise ApiProblem(
                status.HTTP_409_CONFLICT,
                "email-already-registered",
                "Email already registered",
                "An account with this email already exists.",
                errors={"email": "This email is already registered. Please log in instead."},
            ) from None

        return Response(CustomerResponseSerializer(customer).data, status=status.HTTP_201_CREATED)
