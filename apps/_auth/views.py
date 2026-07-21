from logging import getLogger
from uuid import uuid4

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps._mail.mails import send_mail
from apps._redis.cache import delete_from_cache, get_from_cache, set_in_cache
from project.config import config

logger = getLogger(__name__)


def user_to_dict(user: User) -> dict:
    group = user.groups.first()

    profile = getattr(user, "profile", None)
    establishment_data = None

    if profile and profile.establishment:
        establishment_data = {
            "id": profile.establishment.id,
            "name": profile.establishment.name,
        }

    return {
        "id": user.id,
        "last_login": user.last_login,
        "is_superuser": user.is_superuser,
        "username": user.username,
        "last_name": user.last_name,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_active": user.is_active,
        "date_joined": user.date_joined,
        "first_name": user.first_name,
        "role": group.name if group else None,
        "establishment": establishment_data,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: HttpRequest) -> Response:
    return Response(user_to_dict(request.user), status=200)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update(request: HttpRequest) -> Response:
    user = request.user
    data = request.data

    User.objects.filter(id=user.id).update(**data)

    password = data.get("password")
    if password and len(password) > 8:
        user.set_password(password)

    for k, v in data.items():
        if k != "password" and hasattr(user, k):
            setattr(user, k, v)

    user.save()

    return Response(user_to_dict(user), status=200)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auth_logout(request: HttpRequest) -> Response:
    was_authenticated = request.user.is_authenticated
    logout(request)
    return Response({"success": True, "was_authenticated": was_authenticated}, status=200)


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login(request: HttpRequest) -> Response:
    identifier = request.data.get("email")
    password = request.data.get("password")

    user = authenticate(request, username=identifier, password=password)

    if user is not None:
        login(request, user)
        return Response({"success": True}, status=200)

    return Response({"success": False, "message": "Invalid credentials"}, status=401)


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password_request(request: HttpRequest) -> Response:
    email = request.data.get("email")

    if not email:
        return Response({"success": False, "message": "Email is required"}, status=400)

    user = User.objects.filter(email=email).first()

    if user:
        token = str(uuid4())
        minutes = 15
        set_in_cache(f"reset_password_token:{token}", user.id, ttl=60 * minutes)

        redirect_path = "restablecer-acceso"
        try:
            send_mail(
                template="reset_password_request.html",
                ctx={
                    "expire_in": f"{minutes} minutos",
                    "token": token,
                    "redirect_url": config.DEFAULT_FRONTEND + f"/{redirect_path}?token={token}",
                },
                subject="Solicitud de restablecimiento de contraseña",
                to=[email],
            )
        except Exception as e:
            logger.error(f"Failed to send reset password email to {email}", exc_info=e)

    return Response(
        {"success": True, "message": "If the email exists, a reset link has been sent."}, status=200
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password_confirm(request: HttpRequest) -> Response:
    token = request.data.get("token")
    password = request.data.get("password")

    if not token or not password:
        return Response(
            {"success": False, "message": "Token and password are required"}, status=400
        )

    user_id = get_from_cache(f"reset_password_token:{token}")

    if not user_id:
        return Response({"success": False, "message": "Invalid or expired token"}, status=400)

    try:
        user = User.objects.get(id=int(user_id))

        user.set_password(password)
        user.save()

    except User.DoesNotExist:
        return Response({"success": False, "message": "User not found"}, status=404)

    else:
        delete_from_cache(f"reset_password_token:{token}")
        return Response(
            {"success": True, "message": "Password has been reset successfully"}, status=200
        )
