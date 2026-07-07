from json import dumps as json_dumps
from logging import getLogger
from typing import Literal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import StreamingHttpResponse
from django.views.decorators.http import require_GET
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps._api.gossiper import (
    publish_handler,
    redis_client,
)
from apps._api.mixins import MixinViewSet
from apps._api.views import api_health_check
from apps._auth.permissions import (
    any_of,
    permission,
)

from . import models, serializers

logger = getLogger(__name__)


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


class EstablishmentViewSet(MixinViewSet):
    model_name = "establishment"
    queryset = models.Establishment.objects.all()
    serializer_class = serializers.EstablishmentSerializer
    permission_classes = [
        permission(user=["Factory manager"], can=["see"]),
    ]


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
            permission(user=["Store manager", "Public"], can=["see"]),
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
    serializer_class = serializers.DeliverySerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see_self"]),
            permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
        )
    ]

    def get_queryset(self):
        return self.get_self_queryset(
            model=models.Delivery,
            queryset_select_related_fields=["store__establishment"],
            filter_group_to_all={"name": "Factory manager"},
            filter_group_to_self={"name": "Store manager"},
            filter_query="store",
        )

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

        publish_handler(self.model_name, "updated", self.get_serializer(delivery).data, self.SOURCE)
        return Response(self.get_serializer(delivery).data, status=200)


class InventoryViewSet(MixinViewSet):
    model_name = "inventory"
    serializer_class = serializers.InventorySerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see", "update"]),
            permission(user=["Factory manager"], can=["see"]),
        )
    ]
    filterset_fields = ["store"]

    def get_queryset(self):
        return self.get_self_queryset(
            model=models.Inventory,
            queryset_select_related_fields=["store__establishment"],
            filter_group_to_all={"name": "Factory manager"},
            filter_group_to_self={"name": "Store manager"},
            filter_query="store",
        )


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
        return self.get_self_queryset(
            model=models.Sell,
            queryset_select_related_fields=["store__establishment"],
            filter_group_to_all={"name": "Factory manager"},
            filter_group_to_self={"name": "Store manager"},
            filter_query="store",
        )


class ProfileViewSet(MixinViewSet):
    model_name = "profile"
    queryset = models.Profile.objects.all()
    serializer_class = serializers.ProfileSerializer
    permission_classes = [
        any_of(
            permission(user=["Store manager"], can=["see_self", "update_self"]),
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
    return api_health_check(request)
