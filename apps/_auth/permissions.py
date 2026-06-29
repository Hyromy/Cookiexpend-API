from functools import wraps
from typing import Literal

from rest_framework.permissions import SAFE_METHODS, BasePermission

USER_ROLE = Literal["Store manager", "Factory manager", "Public"]
PERMISSION_TYPE = Literal[
    "see",
    "see_self",
    "create",
    "update",
    "update_self",
    "delete",
    "delete_self",
]


def require_auth_with_group(has_obj_permission_func):
    """
    Decorator to ensure the user is authenticated and belongs to at least one group before checking
    specific permissions.
    """

    @wraps(has_obj_permission_func)
    def wrapper(self, request, view, *args, **kwargs):
        user = request.user

        if user and (user.is_superuser or user.is_staff):
            return True

        if not user or not user.is_authenticated:
            if "Public" in self.allowed_roles:
                return has_obj_permission_func(self, request, view, *args, **kwargs)

            return False

        if not user.groups.exists() and "Public" not in self.allowed_roles:
            return False

        return has_obj_permission_func(self, request, view, *args, **kwargs)

    return wrapper


def any_of(*permissions):
    """
    Combines multiple permission classes, granting access if any one of them allows it.

    It's equivalent to 'or' operator
    """

    class AnyOf(BasePermission):
        def has_permission(self, request, view):
            return any(permission().has_permission(request, view) for permission in permissions)

        def has_object_permission(self, request, view, obj):
            return any(
                permission().has_object_permission(request, view, obj) for permission in permissions
            )

    return AnyOf


def permission(
    *,
    user: list[USER_ROLE],
    can: list[PERMISSION_TYPE],
):
    """
    Factory function to create a permission class based on user roles and allowed actions. The generated
    permission class checks if the user belongs to the specified role and has the required permissions
    for the requested HTTP method.
    """

    class Permission(BasePermission):
        def __init__(self):
            self.allowed_roles = user

        def _has_role(self, request):
            if not request.user or not request.user.is_authenticated:
                return "Public" in user

            user_groups = request.user.groups.values_list("name", flat=True)
            if "Public" in user:
                return True

            return any(group in user for group in user_groups)

        def _is_owner(self, request, obj):
            """
            Checks if the user is the owner of the object. This is a simplified example and should be
            adapted to your specific models and relationships. It assumes that the user's profile has
            an 'establishment' field that can be compared to the object's related establishment.
            """

            if not hasattr(request.user, "profile"):
                return False

            user_establishment = request.user.profile.establishment

            if hasattr(obj, "id") and obj.__class__.__name__ == "Store":
                return obj == user_establishment

            if hasattr(obj, "store"):
                return obj.store == user_establishment

            if hasattr(obj, "factory"):
                return obj.factory == user_establishment

            return False

        @require_auth_with_group
        def has_permission(self, request, view):
            if not self._has_role(request):
                return False

            if request.method in SAFE_METHODS and ("see" in can or "see_self" in can):
                return True

            if request.method == "POST" and "create" in can:
                return True

            if request.method in ["PUT", "PATCH"] and ("update" in can or "update_self" in can):
                return True

            if request.method == "DELETE" and ("delete" in can or "delete_self" in can):
                return True

            return False

        @require_auth_with_group
        def has_object_permission(self, request, view, obj):
            if not self._has_role(request):
                return False

            if request.method in SAFE_METHODS:
                if "see" in can:
                    return True
                if "see_self" in can:
                    return self._is_owner(request, obj)

            if request.method in ["PUT", "PATCH"]:
                if "update" in can:
                    return True
                if "update_self" in can:
                    return self._is_owner(request, obj)

            if request.method == "DELETE":
                if "delete" in can:
                    return True
                if "delete_self" in can:
                    return self._is_owner(request, obj)

            return False

    return Permission
