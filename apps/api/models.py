from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.all_with_deleted().deleted()


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    all_objects = models.Manager()
    objects = SoftDeleteManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_product_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} - ${self.price}"

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        type(self).all_objects.filter(pk=self.pk).update(deleted_at=self.deleted_at)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)
