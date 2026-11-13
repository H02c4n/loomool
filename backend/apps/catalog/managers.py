from django.db import models


class CategoryManager(models.Manager):
    def active(self):
        return self.get_queryset().filter(is_active=True)

    def roots(self):
        return self.active().filter(parent__isnull=True)


class ProductScopedManager(models.Manager):
    """
    Enforces store isolation at the queryset level for products.

    - Anonymous       -> empty
    - SUPER_ADMIN     -> all
    - Everyone else   -> only products belonging to stores they own/member
    """

    def for_user(self, user):
        qs = self.get_queryset()
        if user is None or not user.is_authenticated:
            return qs.none()
        if getattr(user, "role", None) == "SUPER_ADMIN":
            return qs
        return qs.filter(
            models.Q(store__owner=user) | models.Q(store__members__user=user)
        ).distinct()
