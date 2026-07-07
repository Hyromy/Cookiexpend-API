from rest_framework.response import Response


def api_health_check(request) -> Response:
    return Response({"healthy": True}, status=200)
