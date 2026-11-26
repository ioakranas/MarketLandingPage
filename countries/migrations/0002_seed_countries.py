"""Seed the countries offered at registration (a sample of three, per the assignment).

A data migration rather than a fixture: it runs automatically with `migrate`, in order,
in every environment, and can be reversed.
"""

from django.db import migrations

COUNTRIES = [
    ("GR", "Greece", "30"),
    ("CY", "Cyprus", "357"),
    ("GB", "United Kingdom", "44"),
]


def seed(apps, schema_editor):
    # The historical model: the schema as of this migration, not today's models.py.
    Country = apps.get_model("countries", "Country")
    for iso_code, name, dial_code in COUNTRIES:
        Country.objects.update_or_create(
            iso_code=iso_code, defaults={"name": name, "dial_code": dial_code}
        )


def unseed(apps, schema_editor):
    Country = apps.get_model("countries", "Country")
    Country.objects.filter(iso_code__in=[iso for iso, _, _ in COUNTRIES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("countries", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
