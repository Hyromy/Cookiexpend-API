from json import dumps as json_dumps
from logging import getLogger
from typing import Literal

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
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


def status_change_handler(curren_status: str, step: Literal[1, -1]) -> str:
    """Determine the next status based on the current status and the step. The step can be 1 for moving forward or -1 for moving backward in the status flow."""

    try:
        step = int(step)
    except (ValueError, TypeError) as e:
        raise ValueError("Step must be an integer (1 or -1)") from e

    match curren_status:
        case "pending":
            if step == 1:
                return "in_progress"
            raise ValueError("Cannot move backward from pending status")

        case "in_progress":
            if step == 1:
                return "completed"
            if step == -1:
                return "cancelled"

        case "completed":
            raise ValueError("Completed cannot change status")

        case "cancelled":
            if step == 1:
                return "in_progress"
            raise ValueError("Cannot move backward from cancelled status")

        case _:
            raise KeyError("Invalid status")


class MixinViewSet(viewsets.ModelViewSet):
    """Mixin viewset to handle common logic, publishing events to Redis on create, update, and delete operations."""

    model_name: MODEL

    filter_backends = [DjangoFilterBackend]

    def perform_create(self, serializer):
        """Override the default create behavior to publish an event after saving the new instance."""

        instance = serializer.save()
        instance.refresh_from_db()

        publish_handler(self.model_name, "created", self.get_serializer(instance).data, source)

    def perform_update(self, serializer):
        """Override the default update behavior to publish an event after saving the updated instance. Increment the version number on update."""

        instance = serializer.save()
        instance.version += 1
        instance.save()

        instance.refresh_from_db()

        publish_handler(self.model_name, "updated", self.get_serializer(instance).data, source)

    def perform_destroy(self, instance):
        """Override the default destroy behavior to publish an event before deleting the instance. Include the instance data in the event payload before deletion."""

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


class StatusViewSet(MixinViewSet):
    model_name = "status"
    queryset = models.Status.objects.all()
    serializer_class = serializers.StatusSerializer
    permission_classes = [
        permission(user=["Store manager", "Factory manager"], can=["see"]),
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

    @action(
        detail=True,
        methods=["get", "patch"],
        url_path="status",
        permission_classes=[
            permission(user=["Store manager", "Factory manager"], can=["see", "update"]),
        ],
    )
    def delivery_status(self, request, pk=None):
        delivery = self.get_object()

        if self.request.method == "GET":
            return Response(self.get_serializer(delivery).data, status=200)

        step = request.data.get("step")
        if step is None:
            return Response({"step": ["This field is required."]}, status=400)

        try:
            step = int(step)
        except (ValueError, TypeError):
            return Response({"step": ["Must be an integer (1 or -1)."]}, status=400)

        try:
            with transaction.atomic():
                new_status_obj = models.Status.objects.get(
                    name=status_change_handler(delivery.status.name, step)
                )

                delivery.status = new_status_obj
                delivery.version += 1
                delivery.save()

                if new_status_obj.id == 3:
                    packages = delivery.package_set.select_related("product").all()
                    for item in packages:
                        inventory_item, created = (
                            models.Inventory.objects.select_for_update().get_or_create(
                                store=delivery.store,
                                product=item.product,
                                defaults={"quantity": item.quantity},
                            )
                        )

                        if not created:
                            inventory_item.quantity += item.quantity
                            inventory_item.save()

        except Exception as e:
            return Response({"error": str(e)}, status=400)

        publish_handler(self.model_name, "updated", self.get_serializer(delivery).data, source)
        return Response(self.get_serializer(delivery).data, status=200)


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
    serializer_class = serializers.SellSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see_self", "create"]),
            permission(user=["Factory manager"], can=["see", "update", "delete"]),
        )
    ]

    def get_queryset(self):
        user = self.request.user

        if not user or user.is_anonymous:
            return models.Sell.objects.none()

        queryset = models.Sell.objects.select_related("store__establishment")

        if (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name="Factory manager").exists()
        ):
            return queryset.all()

        if user.groups.filter(name="Store manager").exists():
            if hasattr(user, "profile") and user.profile.establishment:
                user_establishment_id = user.profile.establishment.id
                return queryset.filter(store__establishment_id=user_establishment_id)

            return models.Sell.objects.none()

        return models.Sell.objects.none()


class PaymentMethodViewSet(MixinViewSet):
    model_name = "payment_method"
    queryset = models.PaymentMethod.objects.all()
    serializer_class = serializers.PaymentMethodSerializer
    permission_classes = [
        permission(user=["Store manager", "Factory manager"], can=["see"]),
    ]


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
