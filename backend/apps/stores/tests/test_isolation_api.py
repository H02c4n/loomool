import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import RoleChoices
from apps.stores.models import Store, StoreMember

User = get_user_model()


def _user(email, role=RoleChoices.CUSTOMER):
    u = User.objects.create_user(email=email, password="long-password-123")
    u.role = role
    u.save(update_fields=["role"])
    return u


def _store(owner, name, slug):
    return Store.objects.create(name=name, slug=slug, owner=owner)


@pytest.mark.django_db
class TestStoreListIsolation:
    def test_anonymous_blocked(self):
        c = APIClient()
        r = c.get(reverse("stores:list"))
        assert r.status_code in (401, 403)

    def test_owner_sees_only_own_stores(self):
        a = _user("a@x.com")
        b = _user("b@x.com")
        s_a = _store(a, "A", "a")
        _store(b, "B", "b")

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("stores:list"))
        assert r.status_code == 200
        ids = [row["id"] for row in r.json()]
        assert ids == [str(s_a.id)]

    def test_member_sees_shared_store(self):
        owner = _user("owner@x.com")
        staff = _user("staff@x.com")
        s = _store(owner, "A", "a")
        StoreMember.objects.create(store=s, user=staff, role="STAFF")

        c = APIClient()
        c.force_authenticate(user=staff)
        r = c.get(reverse("stores:list"))
        assert r.status_code == 200
        assert [row["id"] for row in r.json()] == [str(s.id)]

    def test_super_admin_sees_all(self):
        admin = _user("admin@x.com", role=RoleChoices.SUPER_ADMIN)
        a = _user("a@x.com")
        _store(a, "A", "a")
        _store(a, "B", "b")

        c = APIClient()
        c.force_authenticate(user=admin)
        r = c.get(reverse("stores:list"))
        assert r.status_code == 200
        assert len(r.json()) == 2


@pytest.mark.django_db
class TestStoreDetailIsolation:
    def test_other_seller_gets_404(self):
        a = _user("a@x.com")
        b = _user("b@x.com")
        s_b = _store(b, "B", "b")

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("stores:detail", args=[s_b.id]))
        assert r.status_code == 404

    def test_owner_gets_200(self):
        a = _user("a@x.com")
        s_a = _store(a, "A", "a")

        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("stores:detail", args=[s_a.id]))
        assert r.status_code == 200
        assert r.json()["id"] == str(s_a.id)
        assert r.json()["role"] == "OWNER"

    def test_member_gets_200(self):
        owner = _user("owner@x.com")
        staff = _user("staff@x.com")
        s = _store(owner, "A", "a")
        StoreMember.objects.create(store=s, user=staff, role="STAFF")

        c = APIClient()
        c.force_authenticate(user=staff)
        r = c.get(reverse("stores:detail", args=[s.id]))
        assert r.status_code == 200
        assert r.json()["role"] == "STAFF"

    def test_super_admin_gets_any(self):
        admin = _user("admin@x.com", role=RoleChoices.SUPER_ADMIN)
        a = _user("a@x.com")
        s = _store(a, "A", "a")

        c = APIClient()
        c.force_authenticate(user=admin)
        r = c.get(reverse("stores:detail", args=[s.id]))
        assert r.status_code == 200

    def test_anonymous_blocked(self):
        a = _user("a@x.com")
        s = _store(a, "A", "a")

        c = APIClient()
        r = c.get(reverse("stores:detail", args=[s.id]))
        assert r.status_code in (401, 403)

    def test_nonexistent_store_404(self):
        import uuid

        a = _user("a@x.com")
        c = APIClient()
        c.force_authenticate(user=a)
        r = c.get(reverse("stores:detail", args=[uuid.uuid4()]))
        assert r.status_code == 404
