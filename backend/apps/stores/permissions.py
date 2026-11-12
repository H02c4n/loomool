from rest_framework.permissions import BasePermission

from .models import Store, StoreMember


def _is_store_owner(user, store: Store) -> bool:
    return store.owner_id == user.id


def _member_role(user, store: Store) -> str | None:
    m = StoreMember.objects.filter(store=store, user=user).first()
    return m.role if m else None


class IsStoreOwner(BasePermission):
    """Object-level: user must own the store."""

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "SUPER_ADMIN":
            return True
        return _is_store_owner(request.user, obj)


class IsStoreMember(BasePermission):
    """Object-level: user must own the store or be a StoreMember."""

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "SUPER_ADMIN":
            return True
        if _is_store_owner(request.user, obj):
            return True
        return _member_role(request.user, obj) is not None


class IsStoreStaff(BasePermission):
    """Object-level: user must be OWNER or a STAFF/MANAGER member."""

    def has_object_permission(self, request, view, obj) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "SUPER_ADMIN":
            return True
        if _is_store_owner(request.user, obj):
            return True
        return _member_role(request.user, obj) in {"STAFF", "MANAGER", "OWNER"}
