from django.contrib.auth import logout
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def auth_logout(request: HttpRequest) -> JsonResponse:
    was_authenticated = request.user.is_authenticated
    logout(request)
    return JsonResponse({"success": True, "was_authenticated": was_authenticated}, status=200)
