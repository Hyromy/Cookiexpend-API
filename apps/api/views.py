from json import dumps as json_dumps
from logging import getLogger

from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import models, serializers
from .gossiper import (
    publish_handler,
    redis_client,
)

logger = getLogger(__name__)

source = "api request"


class ProductViewSet(viewsets.ModelViewSet):
    queryset = models.Product.objects.all()
    serializer_class = serializers.ProductSerializer

    def perform_create(self, serializer: serializers.ProductSerializer):
        instance: models.Product = serializer.save()
        publish_handler("product", "created", serializers.ProductSerializer(instance).data, source)

    def perform_update(self, serializer: serializers.ProductSerializer):
        instance: models.Product = serializer.save()
        instance.version += 1
        instance.save()

        publish_handler("product", "updated", serializers.ProductSerializer(instance).data, source)

    def perform_destroy(self, instance: models.Product):
        instance.delete()
        publish_handler("product", "deleted", serializers.ProductSerializer(instance).data, source)


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
