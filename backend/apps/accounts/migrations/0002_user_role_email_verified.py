from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("CUSTOMER", "Customer"),
                    ("SELLER", "Seller"),
                    ("SELLER_STAFF", "Seller staff"),
                    ("SUPPORT", "Support"),
                    ("FINANCE_ADMIN", "Finance admin"),
                    ("PRODUCT_ADMIN", "Product admin"),
                    ("SUPER_ADMIN", "Super admin"),
                ],
                default="CUSTOMER",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="is_email_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]