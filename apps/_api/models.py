from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.timezone import now


def money(
    int_size: int = 4,
    decimal_places: int = 2,
    /,
    *,
    min_value: Decimal = Decimal("0.01"),
    default: Decimal = Decimal("0.00"),
):
    """Create a DecimalField for storing monetary values"""

    return models.DecimalField(
        max_digits=int_size + decimal_places,
        decimal_places=decimal_places,
        validators=[MinValueValidator(min_value)],
        default=default,
    )


def unique_active_constraint(model_name: str, /, *field_name: str):
    """
    Create a unique constraint for a model that only applies to active (non-deleted) objects.
    You can define a lot of unique constraints for a model, but this function will create a unique constraint that only applies to active objects.
    This is useful for models that implement soft delete functionality, where deleted objects are not actually removed.
    """

    return models.UniqueConstraint(
        fields=list(field_name),
        condition=models.Q(deleted_at__isnull=True),
        name=f"unique_active_{model_name}_{'_'.join(field_name)}",
    )


class SoftDeleteQuerySet(models.QuerySet):
    """A custom QuerySet that filters out soft-deleted objects by default"""

    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    """A custom manager that uses the SoftDeleteQuerySet and provides methods for soft-deleted objects"""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return self.all_with_deleted().deleted()


class BaseModel(models.Model):
    """
    An abstract base model that provides common fields and methods for all models.
    Provides created_at, updated_at, deleted_at, and version fields, as well as soft delete functionality.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    all_objects = models.Manager()
    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete_parent(self, model: "BaseModel", fk_field_name: str):
        """Delete the parent object of this instance."""

        BaseModel.delete(self)

        related_id = getattr(self, fk_field_name)

        if related_id:
            model.all_objects.filter(pk=related_id).update(deleted_at=self.deleted_at)

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = now()
        type(self).all_objects.filter(pk=self.pk).update(deleted_at=self.deleted_at)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)
