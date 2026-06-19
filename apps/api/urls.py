from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Ensure that the endpoint is registered in plural form to follow REST conventions
router.register(r"establishments", views.EstablishmentViewSet)
router.register(r"factories", views.FactoryViewSet)
router.register(r"stores", views.StoreViewSet)
router.register(r"products", views.ProductViewSet)
router.register(r"deliveries", views.DeliveryViewSet)
router.register(r"inventories", views.InventoryViewSet, basename="inventory")
router.register(r"sells", views.SellViewSet, basename="sell")
router.register(r"profiles", views.ProfileViewSet, basename="profile")

router.register(r"payment-methods", views.PaymentMethodViewSet)
router.register(r"sell-details", views.SellDetailViewSet)
router.register(r"payments", views.PaymentViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.health_check),
    path("events/", views.events),
]
