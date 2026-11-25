from django.apps import AppConfig


class CommonConfig(AppConfig):
    name = "common"

    def ready(self) -> None:
        # Registers the custom ORM lookups used in model constraints (and migrations).
        from common import lookups  # noqa: F401

        # Registers the OpenAPI extension for our SessionAuthentication, whatever
        # module happens to be imported first.
        from common import schema  # noqa: F401
