"""Serializer building blocks shared by the API apps."""

from rest_framework import serializers


def raw_text(**kwargs) -> serializers.CharField:
    """An optional string field that is passed through untouched.

    Not required and no trimming at this level: the validation layer (common.validation)
    reports missing values with its own messages and decides what to trim (never the
    password).
    """
    return serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, **kwargs)
