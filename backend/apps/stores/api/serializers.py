from rest_framework import serializers

from apps.stores.models import Store, StoreMember


class StoreListSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ("id", "name", "slug", "is_active", "created_at", "role")
        read_only_fields = fields

    def get_role(self, store: Store) -> str:
        """Return the requester's role in this store."""
        user = self.context["request"].user
        if store.owner_id == user.id:
            return StoreMember.Role.OWNER
        m = (
            StoreMember.objects.filter(store=store, user=user)
            .values_list("role", flat=True)
            .first()
        )
        return m or ""


class StoreDetailSerializer(StoreListSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta(StoreListSerializer.Meta):
        fields = StoreListSerializer.Meta.fields + ("owner_email", "member_count", "updated_at")
        read_only_fields = fields

    def get_member_count(self, store: Store) -> int:
        return store.members.count()
