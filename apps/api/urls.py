from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Ensure that the endpoint is registered in plural form to follow REST conventions
router.register(r"products", views.ProductViewSet)
router.register(r"establishments", views.EstablishmentViewSet)
router.register(r"factories", views.FactoryViewSet)
router.register(r"stores", views.StoreViewSet)
router.register(r"deliveries", views.DeliveryViewSet)
router.register(r"inventories", views.InventoryViewSet)
router.register(r"sells", views.SellViewSet)
router.register(r"payment-methods", views.PaymentMethodViewSet)
router.register(r"packages", views.PackageViewSet)
router.register(r"sell-details", views.SellDetailViewSet)
router.register(r"payments", views.PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.health_check),
    path("events/", views.events),
]
