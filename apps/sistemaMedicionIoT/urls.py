from django.urls import path

from .views import measurements


urlpatterns = [
    path("measurements/", measurements),
]