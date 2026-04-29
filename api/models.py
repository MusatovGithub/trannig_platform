import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    name = models.CharField(max_length=120, blank=True)
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_token"
        ordering = ["-created_at"]

    @staticmethod
    def hash_token(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def create_token(cls, user, name=""):
        token = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            user=user,
            name=name,
            key_hash=cls.hash_token(token),
        )
        return instance, token

    @classmethod
    def authenticate(cls, raw_token):
        if not raw_token:
            return None

        token = (
            cls.objects.select_related("user", "user__company")
            .filter(key_hash=cls.hash_token(raw_token))
            .first()
        )
        if not token:
            return None

        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])
        return token

    def __str__(self):
        label = self.name or "API token"
        return f"{label} for {self.user}"
