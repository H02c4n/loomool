from django.db import migrations


def assign_super_admin(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_superuser=True).update(role="SUPER_ADMIN")


def reverse_assign(apps, schema_editor):
    # No-op: role values are not safe to guess on reverse.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_role_email_verified"),
    ]

    operations = [
        migrations.RunPython(assign_super_admin, reverse_assign),
    ]
