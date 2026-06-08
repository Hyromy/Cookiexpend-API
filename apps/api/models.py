from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


def money():
    return models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )


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


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    all_objects = models.Manager()
    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        type(self).all_objects.filter(pk=self.pk).update(deleted_at=self.deleted_at)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)


# first order


class Establishment(BaseModel):
    name = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=200)
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=20, blank=True, default="")

    def __str__(self):
        return f"{self.name} - {self.municipality}, {self.street}"


# second order


class Factory(BaseModel):
    establishment = models.OneToOneField(Establishment, on_delete=models.CASCADE)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["establishment"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_factory_establishment",
            ),
        ]

    def __str__(self):
        return self.establishment.name


class Store(BaseModel):
    establishment = models.OneToOneField(Establishment, on_delete=models.CASCADE)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["establishment"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_store_establishment",
            ),
        ]

    def __str__(self):
        return self.establishment.name


class Product(BaseModel):
    name = models.CharField(max_length=255)
    price = money()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_product_name",
            ),
        ]

    def __str__(self):
        return f"{self.name} - ${self.price}"


class Status(BaseModel):
    name = models.CharField(max_length=32)
    description = models.TextField(blank=True, default="", max_length=255)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_status_name",
            ),
        ]

    def __str__(self):
        return self.name


# third order


class Delivery(BaseModel):
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    status = models.ForeignKey(Status, on_delete=models.PROTECT, default=1)

    def __str__(self):
        return f"{self.factory} to {self.store}"


class Inventory(BaseModel):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["store", "product"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_inventory_store_product",
            ),
        ]

    def __str__(self):
        return f"{self.store} - {self.product}: {self.quantity}"


class Sell(BaseModel):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    total = money()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["store", "date"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_sell_store_date",
            ),
        ]

    def __str__(self):
        return f"{self.id}: ${self.total}"


class PaymentMethod(BaseModel):
    name = models.CharField(max_length=100)

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_payment_method_name",
            ),
        ]

    def __str__(self):
        return self.name


# fourth order


class Package(BaseModel):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["delivery", "product"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_package_delivery_product",
            ),
        ]

    def __str__(self):
        return f"{self.delivery} - {self.product}: {self.quantity}"


class SellDetail(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    sell = models.ForeignKey(Sell, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = money()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["sell", "product"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_sell_details_sell_product",
            ),
        ]

    def __str__(self):
        return f"{self.sell.id} - {self.product} (${self.price}) x{self.quantity}"


class Payment(BaseModel):
    sell = models.ForeignKey(Sell, on_delete=models.CASCADE)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    amount = money()

    class Meta(BaseModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["sell", "payment_method"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_payment_sell_payment_method",
            ),
        ]

    def __str__(self):
        return f"{self.sell.id} - {self.payment_method}: ${self.amount}"
