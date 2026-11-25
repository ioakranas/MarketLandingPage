"""Login attempts: the data behind lockout and login history."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class LoginAttempt(models.Model):
    """One login attempt on an existing account, successful or not.

    Attempts for unknown emails are not stored: they have no account to lock, and a bot
    could flood the table with them (they are logged instead, with the email masked).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # deleting an account deletes its history
        related_name="login_attempts",
        # The composite index below starts with user, so it already serves lookups by
        # user: a separate single-column index would only cost writes.
        db_index=False,
    )
    succeeded = models.BooleanField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # Serves "this user's attempts in the last 15 minutes" (lockout) and
        # "this user's successful logins" (history).
        indexes = [models.Index(fields=["user", "attempted_at"], name="login_attempt_user_time_idx")]

    def __str__(self) -> str:
        outcome = "succeeded" if self.succeeded else "failed"
        return f"Login {outcome} for user {self.user_id} at {self.attempted_at:%Y-%m-%d %H:%M:%S}"
