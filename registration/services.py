"""Registration use case: turns a validated Registration into a user + customer.

Orchestrates accounts (identity), customers (profile) and countries (reference data);
none of those apps know about registration.
"""

from django.db import IntegrityError, transaction

from accounts.models import User
from common.validation import Registration
from countries.models import Country
from customers.models import Customer


class EmailAlreadyRegistered(Exception):
    pass


@transaction.atomic
def register_customer(registration: Registration) -> Customer:
    """Create the login identity and the customer profile in one transaction.

    Either both rows exist afterwards or neither does. Duplicate emails are detected by
    the database's unique constraint, not by a prior SELECT: a check-then-insert would
    race when two sign-ups for the same email arrive at the same moment.
    """
    country = Country.objects.get(iso_code=registration.country_iso)
    try:
        # Savepoint: a failed insert must not poison the outer transaction.
        with transaction.atomic():
            # Hashing (Argon2) happens before the insert, so a duplicate takes as long
            # as a success: response times don't reveal registered emails.
            user = User.objects.create_user(registration.email, registration.password)
    except IntegrityError as error:
        if User.objects.filter(email__iexact=registration.email).exists():
            raise EmailAlreadyRegistered from error
        raise

    return Customer.objects.create(
        user=user,
        first_name=registration.first_name,
        last_name=registration.last_name,
        country=country,
        phone=registration.phone,
    )
