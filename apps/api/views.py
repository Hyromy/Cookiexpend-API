from json import dumps as json_dumps
from logging import getLogger

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import models, serializers
from .gossiper import (
    MODEL,
    publish_handler,
    redis_client,
)
from .permissions import (
    any_of,
    permission,
)

logger = getLogger(__name__)

source = "api request"


class MixinViewSet(viewsets.ModelViewSet):
    """Mixin viewset to handle common logic, publishing events to Redis on create, update, and delete operations."""

    model_name: MODEL

    filter_backends = [DjangoFilterBackend]

    def perform_create(self, serializer):
        serializer.save()
        publish_handler(self.model_name, "created", serializer.data, source)

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.version += 1
        instance.save()

        publish_handler(self.model_name, "updated", serializer.data, source)

    def perform_destroy(self, instance):
        data = self.get_serializer(instance).data
        instance.delete()
        publish_handler(self.model_name, "deleted", data, source)


class FactoryViewSet(MixinViewSet):
    model_name = "factory"
    queryset = models.Factory.objects.all()
    serializer_class = serializers.FactorySerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]


class StoreViewSet(MixinViewSet):
    model_name = "store"
    queryset = models.Store.objects.all()
    serializer_class = serializers.StoreSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]


class ProductViewSet(MixinViewSet):
    model_name = "product"
    queryset = models.Product.objects.all()
    serializer_class = serializers.ProductSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]


class DeliveryViewSet(MixinViewSet):
    model_name = "delivery"
    queryset = models.Delivery.objects.all()
    serializer_class = serializers.DeliverySerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]


class InventoryViewSet(MixinViewSet):
    model_name = "inventory"
    queryset = models.Inventory.objects.all()
    serializer_class = serializers.InventorySerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see", "update"]),
            permission(user=["Factory manager"], can=["see"]),
        )
    ]
    filterset_fields = ["store"]


class SellViewSet(MixinViewSet):
    model_name = "sell"
    queryset = models.Sell.objects.all()
    serializer_class = serializers.SellSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see", "create"]),
            permission(user=["Factory manager"], can=["see", "update", "delete"]),
        )
    ]


class PaymentMethodViewSet(MixinViewSet):
    model_name = "payment_method"
    queryset = models.PaymentMethod.objects.all()
    serializer_class = serializers.PaymentMethodSerializer
    permission_classes = [
        permission(user=["Store manager", "Factory manager"], can=["see"]),
    ]


class PackageViewSet(MixinViewSet):
    model_name = "package"
    queryset = models.Package.objects.all()
    serializer_class = serializers.PackageSerializer


class SellDetailViewSet(MixinViewSet):
    model_name = "sell_detail"
    queryset = models.SellDetail.objects.all()
    serializer_class = serializers.SellDetailSerializer


class PaymentViewSet(MixinViewSet):
    model_name = "payment"
    queryset = models.Payment.objects.all()
    serializer_class = serializers.PaymentSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see", "update"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]


@require_GET
@login_required
def events(request):
    """Endpoint for streaming guild update events. Clients can connect to this endpoint to receive real-time updates."""

    def event_stream():
        pubsub = redis_client.pubsub()
        pubsub.psubscribe("*")

        try:
            yield f"data: {json_dumps({'status': 'connected'})}\n\n"

            for message in pubsub.listen():
                if message["type"] == "pmessage":
                    data = message["data"]
                    yield f"data: {data.decode('utf-8') if isinstance(data, bytes) else data}\n\n"

        except Exception as e:
            logger.error("Error occurred while streaming events", exc_info=e)

        finally:
            pubsub.close()

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")

    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    response["Access-Control-Allow-Origin"] = "*"

    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"healthy": True}, status=200)
