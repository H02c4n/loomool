from django.db import models


class StoreScopedManager(models.Manager):
    """
    Enforces store isolation at the queryset level.

    - Anonymous user         -> empty queryset
    - SUPER_ADMIN            -> all stores
    - Everyone else          -> only stores they own or are a member of
    """

    def for_user(self, user):
        qs = self.get_queryset()
        if user is None or not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "SUPER_ADMIN":
            return qs
        return qs.filter(models.Q(owner=user) | models.Q(members__user=user)).distinct()
