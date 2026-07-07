from django.db import models

from apps._api.models import BaseModel, unique_active_constraint
from project.utils import ImgHelper


class Category(BaseModel):
    label = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    logo = models.ImageField(
        upload_to=ImgHelper.generate_path_in("categories"), blank=True, null=True
    )

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("category", "label"),
        ]

    def __str__(self):
        return self.label


class Presentation(BaseModel):
    label = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("presentation", "label"),
        ]

    def __str__(self):
        return self.label


class GaleriaItem(BaseModel):
    url = models.ImageField(upload_to=ImgHelper.generate_path_in("galeria"))
    alt = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]


class FAQ(BaseModel):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]


class Department(BaseModel):
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]


class Subject(BaseModel):
    label = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="subjects"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]


class Retailer(BaseModel):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    state = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta(BaseModel.Meta):
        ordering = ["state", "municipality"]
