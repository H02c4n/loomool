from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """
    Grants access when `request.user.role` is in `view.allowed_roles`.

    If the view does not set `allowed_roles`, only authentication is
    enforced (effectively the same as IsAuthenticated).
    """

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        allowed = getattr(view, "allowed_roles", None)
        if not allowed:
            return True
        return request.user.role in allowed
