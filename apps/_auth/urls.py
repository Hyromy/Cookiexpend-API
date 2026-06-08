from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .views import auth_login, auth_logout, me

urlpatterns = [
    path("me/", me),
    path("login/", auth_login),
    path("logout/", auth_logout),
    path("token/", TokenObtainPairView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
]
