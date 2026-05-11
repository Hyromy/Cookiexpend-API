from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Ensure that the endpoint is registered in plural form to follow REST conventions
router.register(r"products", views.ProductViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.health_check),
    path("events/", views.events),
]
