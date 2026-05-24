from functools import wraps
from typing import Literal

from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated

USER_ROLE = Literal["Store manager", "Factory manager"]
PERMISSION_TYPE = Literal["see", "create", "update", "delete"]


def require_auth_with_group(has_permission_func):
    """Decorator to ensure the user is authenticated and belongs to at least one group before checking specific permissions."""

    @wraps(has_permission_func)
    def wrapper(self, request, view):
        user = request.user

        if not IsAuthenticated().has_permission(request, view):
            return False

        if user.is_superuser or user.is_staff:
            return True

        if not user.groups.exists():
            return False

        return has_permission_func(self, request, view)

    return wrapper


def any_of(*permissions):
    """
    Combines multiple permission classes, granting access if any one of them allows it.

    It's equivalent to 'or' operator
    """

    class AnyOf(BasePermission):
        def has_permission(self, request, view):
            return any(permission().has_permission(request, view) for permission in permissions)

    return AnyOf


def permission(
    *,
    user: list[USER_ROLE],
    can: list[PERMISSION_TYPE],
):
    """Factory function to create a permission class based on user roles and allowed actions. The generated permission class checks if the user belongs to the specified role and has the required permissions for the requested HTTP method."""

    class Permission(BasePermission):
        @require_auth_with_group
        def has_permission(self, request, view):
            user_groups = request.user.groups.values_list("name", flat=True)
            if not any(group in user for group in user_groups):
                return False

            if request.method in SAFE_METHODS and "see" in can:
                return True
            elif request.method == "POST" and "create" in can:
                return True
            elif request.method in ["PUT", "PATCH"] and "update" in can:
                return True
            elif request.method == "DELETE" and "delete" in can:
                return True

            return False

    return Permission
