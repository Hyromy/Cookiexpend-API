from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps._api.models import BaseModel, money, unique_active_constraint
from project.utils import ImgHelper

# zero order


class Establishment(BaseModel):
    name = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=200)
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=20, blank=True, default="")

    def __str__(self):
        return f"{self.name} - {self.municipality}, {self.street}"


# first order


class Profile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    establishment = models.ForeignKey(Establishment, on_delete=models.PROTECT)
    role = models.CharField(max_length=20, choices=[("factory", "Factory"), ("store", "Store")])

    def __str__(self):
        return f"{self.user.username} - {self.role} - {self.establishment.name}"


# second order


class Factory(BaseModel):
    establishment = models.OneToOneField(Establishment, on_delete=models.CASCADE)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("factory", "establishment"),
        ]

    def __str__(self):
        return self.establishment.name

    def delete(self, using=None, keep_parents=False):
        self.delete_parent(Establishment, "establishment_id")


class Store(BaseModel):
    establishment = models.OneToOneField(Establishment, on_delete=models.CASCADE)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("store", "establishment"),
        ]

    def __str__(self):
        return self.establishment.name

    def delete(self, using=None, keep_parents=False):
        self.delete_parent(Establishment, "establishment_id")


class Product(BaseModel):
    sku = models.CharField(max_length=18)
    name = models.CharField(max_length=255)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True, default="", max_length=500)
    badge = models.CharField(max_length=50, blank=True, default="")
    price = money()
    img = models.ImageField(upload_to=ImgHelper.generate_path_in("products"), blank=True, null=True)
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.SET_NULL, null=True, blank=True
    )
    presentation = models.ForeignKey(
        "catalog.Presentation", on_delete=models.SET_NULL, null=True, blank=True
    )
    variants = models.ManyToManyField("self", blank=True, symmetrical=True)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("product", "name"),
            unique_active_constraint("product", "sku"),
            unique_active_constraint("product", "slug"),
        ]

    def __str__(self):
        return f"{self.name} - ${self.price}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{slugify(self.name)}-{self.sku}"

        ImgHelper.save(
            model=self,
            methods=[
                ImgHelper.Method.crop_to_square,
                lambda img: ImgHelper.Method.scale(img, size=(1024, 1024)),
            ],
        )
        super().save(*args, **kwargs)


class Status(BaseModel):
    name = models.CharField(max_length=32)
    description = models.TextField(blank=True, default="", max_length=255)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("status", "name"),
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
            unique_active_constraint("inventory", "store", "product"),
        ]

    def __str__(self):
        return f"{self.store} - {self.product}: {self.quantity}"


class Sell(BaseModel):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    total = money()

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("sell", "store", "date"),
        ]

    def __str__(self):
        return f"{self.id}: ${self.total}"


class PaymentMethod(BaseModel):
    name = models.CharField(max_length=100)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("payment_method", "name"),
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
            unique_active_constraint("package", "delivery", "product"),
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
            unique_active_constraint("sell_detail", "sell", "product"),
        ]

    def __str__(self):
        return f"{self.sell.id} - {self.product} (${self.price}) x{self.quantity}"


class Payment(BaseModel):
    sell = models.ForeignKey(Sell, on_delete=models.CASCADE)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    amount = money()

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("payment", "sell", "payment_method"),
        ]

    def __str__(self):
        return f"{self.sell.id} - {self.payment_method}: ${self.amount}"
