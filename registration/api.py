"""POST /api/v1/registrations: create a customer account."""

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.api import ApiProblem
from registration.serializers import CustomerResponseSerializer, RegistrationRequestSerializer
from registration.services import EmailAlreadyRegistered, register_customer


# DRF only checks CSRF for logged-in users. The API is called by our own pages with the
# session cookie, so anonymous POSTs (sign-up, login) are protected too: a third-party
# site must not be able to submit them in a visitor's browser.
@method_decorator(csrf_protect, name="dispatch")
class RegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # anonymous endpoint

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
