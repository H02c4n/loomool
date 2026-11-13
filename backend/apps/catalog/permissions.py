from rest_framework.permissions import BasePermission

from apps.stores.models import Store, StoreMember


def _user_can_manage_store(user, store: Store) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "role", None) == "SUPER_ADMIN":
        return True
    if store.owner_id == user.id:
        return True
    return StoreMember.objects.filter(store=store, user=user).exists()


class IsProductStoreMember(BasePermission):
    """Object-level: user owns or is a member of the product's store."""

    def has_object_permission(self, request, view, obj) -> bool:
        return _user_can_manage_store(request.user, obj.store)
