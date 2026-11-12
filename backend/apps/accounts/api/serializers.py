from rest_framework import serializers

from apps.accounts.models import User


class MeSerializer(serializers.ModelSerializer):
    stores = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_email_verified",
            "date_joined",
            "stores",
        )
        read_only_fields = fields

    def get_stores(self, user):
        memberships = user.store_memberships.select_related("store").all()
        return [
            {
                "id": str(m.store_id),
                "name": m.store.name,
                "role": m.role,
            }
            for m in memberships
        ]
