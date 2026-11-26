from django.contrib.auth.hashers import Argon2PasswordHasher


class FastArgon2PasswordHasher(Argon2PasswordHasher):
    """Same Argon2id algorithm and storage format, test-only cost parameters."""

    time_cost = 1
    memory_cost = 64  # KiB
    parallelism = 1
