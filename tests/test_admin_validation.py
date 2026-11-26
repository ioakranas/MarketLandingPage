"""Staff edits through the admin follow the same rules as sign-up: form errors, never a 500."""

import pytest
from django.db.models import Q, Value

from accounts.models import User
from countries.models import Country
from customers.models import Customer

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(User.objects.create_superuser("admin@example.com", "Admin#12345"))
    return client


@pytest.fixture
def customer(make_customer):
    return make_customer(email="maria@example.com", first_name="Maria", last_name="Georgiou")


def edit_customer(client, customer, **changes):
    data = {
        "user": customer.user_id,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "country": customer.country_id,
        "phone": customer.phone,
        **changes,
    }
    return client.post(f"/admin/customers/customer/{customer.pk}/change/", data)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"phone": "abc123"}, "Phone number may only contain digits."),
        ({"phone": "123"}, "Phone number must be between 6 and 14 digits."),
        ({"first_name": "M4ria"}, "First name may only contain letters, spaces, hyphens and apostrophes."),
        ({"first_name": "Мария"}, "First name must be written in Latin characters, as shown in your passport."),
        ({"last_name": "Li"}, "Last name must be longer than 3 characters."),
    ],
)
def test_invalid_customer_edit_is_a_form_error_with_the_sign_up_message(
    admin_client, customer, changes, message
):
    response = edit_customer(admin_client, customer, **changes)

    assert response.status_code == 200  # the form again, not a crash
    assert message in response.content.decode()
    customer.refresh_from_db()
    assert customer.phone == "6912345678" and customer.first_name == "Maria"  # unchanged


def test_valid_customer_edit_is_normalised_like_sign_up(admin_client, customer):
    response = edit_customer(admin_client, customer, phone="99 123-456", first_name="  Anna  ")

    assert response.status_code == 302
    customer.refresh_from_db()
    assert (customer.phone, customer.first_name) == ("99123456", "Anna")


def test_invalid_dial_code_is_a_form_error(admin_client):
    greece = Country.objects.get(iso_code="GR")
    response = admin_client.post(
        f"/admin/countries/country/{greece.pk}/change/",
        {"iso_code": "GR", "name": "Greece", "dial_code": "3x"},
    )

    assert response.status_code == 200
    assert "Dial code must be 1-4 digits, without &#x27;+&#x27; (e.g. 30)." in response.content.decode()
    greece.refresh_from_db()
    assert greece.dial_code == "30"


def test_admin_stores_emails_lower_case(admin_client, customer):
    response = admin_client.post(
        f"/admin/accounts/user/{customer.user_id}/change/",
        {
            "email": "Maria.G@Example.COM",
            "is_active": "on",
            "date_joined_0": "2026-11-25",
            "date_joined_1": "10:00:00",
        },
    )

    assert response.status_code == 302
    assert User.objects.get(pk=customer.user_id).email == "maria.g@example.com"


def test_constraints_reject_invalid_values_during_model_validation():
    """The digits_only lookup also works when Django checks a value, not a column
    (regression: the value was bound once for two uses, and the check silently passed)."""
    assert Q(phone__digits_only=True).check({"phone": Value("123456")}) is True
    assert Q(phone__digits_only=True).check({"phone": Value("abc123")}) is False


def test_constraint_messages_are_readable(greece):
    customer = Customer(first_name="Maria", last_name="Georgiou", country=greece, phone="12ab")
    with pytest.raises(Exception) as error:
        customer.validate_constraints()
    assert "Phone number must be between 6 and 14 digits." in str(error.value)
