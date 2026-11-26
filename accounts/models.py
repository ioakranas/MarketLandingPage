"""Identity: who can log in. Deliberately free of customer data (see customers.Customer).

Comparable to Spring Security's UserDetails: credentials and account status only, so
back-office staff and customers share one authentication mechanism without staff
needing customer fields.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from common.validation import LIMITS


def normalize_email(email: str) -> str:
    """Emails are stored lower-case, as the validation layer produces them."""
    return email.strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=normalize_email(email), **extra_fields)
        user.set_password(password)  # hashed with Argon2 (settings.PASSWORD_HASHERS)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields) -> "User":
        extra_fields.update(is_staff=True, is_superuser=True)
        return self.create_user(email, password, **extra_fields)

    def get_by_natural_key(self, email: str) -> "User":
        # Used by Django's login: make it case-insensitive like the uniqueness rule.
        return self.get(email__iexact=normalize_email(email))


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=LIMITS["email_max"], unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to the admin site.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            # unique=True alone is case-sensitive; this makes "A@x.com" == "a@x.com"
            # at database level, on any engine.
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.CheckConstraint(
                condition=Q(email__length__lte=LIMITS["email_max"], email__contains="@"),
                name="accounts_user_email_format",
                violation_error_message="Enter a valid email address.",
            ),
        ]

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        # Admin edits too: stored lower-case like sign-ups (uniqueness is case-insensitive
        # anyway; this keeps the stored data uniform).
        super().clean()
        self.email = normalize_email(self.email)
