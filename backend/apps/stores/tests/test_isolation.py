import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import RoleChoices
from apps.stores.models import Store, StoreMember

User = get_user_model()


@pytest.mark.django_db
class TestStoreScopedManager:
    def test_anonymous_gets_nothing(self):
        Store.objects.create(name="A", slug="a", owner=self._owner("a@x.com"))
        assert Store.objects.for_user(None).count() == 0

    def test_owner_sees_own_store_only(self):
        owner_a = self._owner("a@x.com")
        owner_b = self._owner("b@x.com")
        Store.objects.create(name="A", slug="a", owner=owner_a)
        Store.objects.create(name="B", slug="b", owner=owner_b)

        qs_a = Store.objects.for_user(owner_a)
        assert qs_a.count() == 1
        assert qs_a.first().owner == owner_a

    def test_member_sees_shared_store(self):
        owner = self._owner("owner@x.com")
        staff = self._owner("staff@x.com")
        store = Store.objects.create(name="A", slug="a", owner=owner)
        StoreMember.objects.create(store=store, user=staff, role="STAFF")

        qs = Store.objects.for_user(staff)
        assert qs.count() == 1
        assert qs.first() == store

    def test_super_admin_sees_all(self):
        owner = self._owner("owner@x.com")
        admin = User.objects.create_user(email="admin@x.com", password="pw-1234567890")
        admin.role = RoleChoices.SUPER_ADMIN
        admin.save()

        Store.objects.create(name="A", slug="a", owner=owner)
        Store.objects.create(name="B", slug="b", owner=owner)

        assert Store.objects.for_user(admin).count() == 2

    def _owner(self, email):
        return User.objects.create_user(email=email, password="pw-1234567890")
