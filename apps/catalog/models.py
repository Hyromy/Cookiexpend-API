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

    def save(self, *args, **kwargs):
        ImgHelper.save(
            model=self,
            field_name="logo",
            methods=[
                ImgHelper.Method.crop_to_square,
                lambda img: ImgHelper.Method.scale(img, size=(512, 512)),
            ],
        )
        super().save(*args, **kwargs)


class Presentation(BaseModel):
    label = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        constraints = [
            unique_active_constraint("presentation", "label"),
        ]

    def __str__(self):
        return self.label


class GalleryItem(BaseModel):
    url = models.ImageField(upload_to=ImgHelper.generate_path_in("gallery"))
    alt = models.CharField(max_length=200, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]

    def save(self, *args, **kwargs):
        ImgHelper.save(
            model=self,
            field_name="url",
            methods=[
                lambda img: ImgHelper.Method.scale(img, size=(1920, 1920)),
            ],
        )
        super().save(*args, **kwargs)


class FAQ(BaseModel):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta(BaseModel.Meta):
        ordering = ["order"]


class Department(BaseModel):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, default="")
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


class Brand(BaseModel):
    name = models.CharField(max_length=200)
    logo = models.ImageField(
        upload_to=ImgHelper.generate_path_in("brands"), blank=True, null=True
    )

    class Meta(BaseModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        ImgHelper.save(
            model=self,
            field_name="logo",
            methods=[
                ImgHelper.Method.crop_to_square,
                lambda img: ImgHelper.Method.scale(img, size=(512, 512)),
            ],
        )
        super().save(*args, **kwargs)


class Retailer(BaseModel):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    state = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="retailers"
    )
    logo = models.ImageField(
        upload_to=ImgHelper.generate_path_in("retailers"), blank=True, null=True
    )

    class Meta(BaseModel.Meta):
        ordering = ["state", "municipality"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        ImgHelper.save(
            model=self,
            field_name="logo",
            methods=[
                ImgHelper.Method.crop_to_square,
                lambda img: ImgHelper.Method.scale(img, size=(512, 512)),
            ],
        )
        super().save(*args, **kwargs)
