"""Custom ORM lookups for database-level CHECK constraints.

Django's ``max_length`` is NOT enforced by SQLite (it ignores the size in VARCHAR(n)),
and the built-in ``__regex`` lookup on SQLite relies on a REGEXP function that only
Django's own connections provide. These lookups compile to plain SQL that every
client of the database respects:

    Q(first_name__length__gt=3)   ->  length(first_name) > 3
    Q(phone__digits_only=True)    ->  phone <> '' AND phone NOT GLOB '*[^0-9]*'   (SQLite)
                                      phone ~ '^[0-9]+$'                          (PostgreSQL)
"""

from django.db.models import CharField, Lookup
from django.db.models.functions import Length

# Registered on CharField, so also available on its subclasses (e.g. EmailField).
CharField.register_lookup(Length)


@CharField.register_lookup
class DigitsOnly(Lookup):
    lookup_name = "digits_only"
    # The right-hand side is a flag, not a value of the field: don't convert True to "True".
    prepare_rhs = False

    def _sql(self, compiler, connection, template):
        rhs = getattr(self.rhs, "value", self.rhs)  # plain True, or Value(True)
        if rhs is not True:
            raise ValueError("digits_only only supports the value True")
        lhs, params = self.process_lhs(compiler, connection)
        return template.format(lhs=lhs), params

    def as_sqlite(self, compiler, connection):
        return self._sql(compiler, connection, "({lhs} <> '' AND {lhs} NOT GLOB '*[^0-9]*')")

    def as_postgresql(self, compiler, connection):  # pragma: no cover - tests run on SQLite
        return self._sql(compiler, connection, "({lhs} ~ '^[0-9]+$')")

    def as_sql(self, compiler, connection):  # pragma: no cover - other engines
        raise NotImplementedError(f"digits_only is not implemented for {connection.vendor}")
