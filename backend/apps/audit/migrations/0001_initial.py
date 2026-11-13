import uuid

import django.db.models.deletion
from django.db import migrations, models


CREATE_FN = """
CREATE OR REPLACE FUNCTION audit_log_no_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

DROP_FN = "DROP FUNCTION IF EXISTS audit_log_no_mutation();"

CREATE_TRIGGER = """
CREATE TRIGGER audit_log_no_mutation_trigger
BEFORE UPDATE OR DELETE ON audit_auditlog
FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();
"""

DROP_TRIGGER = "DROP TRIGGER IF EXISTS audit_log_no_mutation_trigger ON audit_auditlog;"


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                ("action", models.CharField(db_index=True, max_length=64)),
                ("target_type", models.CharField(blank=True, max_length=64)),
                ("target_id", models.CharField(blank=True, max_length=64)),
                ("metadata", models.JSONField(default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "audit log entry",
                "verbose_name_plural": "audit log entries",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["target_type", "target_id"],
                name="audit_audit_target__2d648a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["actor_user_id", "created_at"],
                name="audit_audit_actor_u_dd6c53_idx",
            ),
        ),
        migrations.RunSQL(CREATE_FN, DROP_FN),
        migrations.RunSQL(CREATE_TRIGGER, DROP_TRIGGER),
    ]
