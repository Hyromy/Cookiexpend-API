from django.db import models

from apps._api.models import BaseModel


class Measurement(BaseModel):

    station = models.CharField(max_length=20)

    process = models.CharField(max_length=20)

    time_ms = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.station} - {self.process}"
