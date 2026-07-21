from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import (
    auth_login,
    auth_logout,
    me,
    reset_password_confirm,
    reset_password_request,
    update,
)

urlpatterns = [
    path("me/", me),
    path("update/", update),
    path("login/", auth_login),
    path("logout/", auth_logout),
    path("token/", TokenObtainPairView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("reset/request/", reset_password_request),
    path("reset/confirm/", reset_password_confirm),
]
