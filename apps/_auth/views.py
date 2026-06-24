from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpRequest
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


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
