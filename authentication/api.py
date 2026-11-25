"""The session resource: log in, see the current session, log out.

    POST   /api/v1/sessions           log in              201 / 400 / 401 / 429
    GET    /api/v1/sessions/current   who am I            200 / 401
    DELETE /api/v1/sessions/current   log out             204 / 401

The session itself is Django's server-side session (cookie = opaque id): logging out
deletes it on the server, so a copied cookie stops working immediately.
"""

import math

from django.contrib.auth import login, logout
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.selectors import session_summary
from authentication.serializers import LoginRequestSerializer, SessionResponseSerializer
from authentication.services import AccountLocked, InvalidCredentials, authenticate_customer
from common.api import ApiProblem
from common.authentication import SESSION_AUTH_CHALLENGE
from common.schema import CSRF_PROBLEM, NOT_AUTHENTICATED_PROBLEM, problem, validation_problem


# CSRF on login too ("login CSRF"): otherwise another site could log a visitor into
# an attacker's account and watch what they do there.
@method_decorator(csrf_protect, name="dispatch")
class SessionCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # anonymous endpoint

    @extend_schema(
        tags=["Sessions"],
        operation_id="createSession",
        summary="Log in",
        description="Starts a server-side session: the response sets the `sessionid` cookie "
        "(HttpOnly) and a new `csrftoken` cookie. The `Location` header points to the "
        "current session. After 5 failed attempts in 15 minutes the account is locked "
        "(429, with a `Retry-After` header in seconds).",
        request=LoginRequestSerializer,
        examples=[
            OpenApiExample(
                "Credentials",
                request_only=True,
                value={"email": "ioannis@example.com", "password": "Secret#123"},
            )
        ],
        responses=dict(
            [
                (201, OpenApiResponse(SessionResponseSerializer, "Logged in.")),
                validation_problem({"email": "Please enter a valid email address (e.g. name@example.com)."}),
                problem(
                    401,
                    "invalid-credentials",
                    "Invalid credentials",
                    "Invalid email or password.",
                    "Unknown email or wrong password: deliberately the same answer for both.",
                ),
                CSRF_PROBLEM,
                problem(
                    429,
                    "account-locked",
                    "Account temporarily locked",
                    "Too many failed login attempts. Please try again in 15 minute(s).",
                    "Too many failed attempts; the Retry-After header says when to try again.",
                ),
            ]
        ),
    )
    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # -> 400 Problem Details

        try:
            user = authenticate_customer(
                serializer.validated_data, ip_address=request.META.get("REMOTE_ADDR")
            )
        except InvalidCredentials:
            raise ApiProblem(
                status.HTTP_401_UNAUTHORIZED,
                "invalid-credentials",
                "Invalid credentials",
                "Invalid email or password.",
                headers={"WWW-Authenticate": SESSION_AUTH_CHALLENGE},
            ) from None
        except AccountLocked as locked:
            raise ApiProblem(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "account-locked",
                "Account temporarily locked",
                "Too many failed login attempts. "
                f"Please try again in {locked.minutes_remaining} minute(s).",
                headers={"Retry-After": str(math.ceil(locked.retry_after.total_seconds()))},
            ) from None

        # New session id (session fixation protection), new CSRF token, last_login.
        login(request, user)

        return Response(
            SessionResponseSerializer(session_summary(user)).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": reverse("v1:current-session")},
        )


class CurrentSessionView(APIView):
    # Default permission: IsAuthenticated -> 401 without a session.
    # DELETE is CSRF-checked by SessionAuthentication, so other sites can't log users out.

    @extend_schema(
        tags=["Sessions"],
        operation_id="getCurrentSession",
        summary="Current session",
        description="Who is logged in, and their previous login (null on the first one).",
        responses=dict(
            [(200, OpenApiResponse(SessionResponseSerializer, "Logged in.")), NOT_AUTHENTICATED_PROBLEM]
        ),
    )
    def get(self, request):
        return Response(SessionResponseSerializer(session_summary(request.user)).data)

    @extend_schema(
        tags=["Sessions"],
        operation_id="deleteCurrentSession",
        summary="Log out",
        description="Deletes the server-side session: the session cookie stops working "
        "immediately, on every device it was copied to.",
        responses=dict(
            [
                (204, OpenApiResponse(description="Logged out.")),
                NOT_AUTHENTICATED_PROBLEM,
                CSRF_PROBLEM,
            ]
        ),
    )
    def delete(self, request):
        logout(request)  # deletes the server-side session
        return Response(status=status.HTTP_204_NO_CONTENT)
