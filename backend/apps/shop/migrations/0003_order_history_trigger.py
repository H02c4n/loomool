from django.db import migrations


CREATE_FN_ORDER = """
CREATE OR REPLACE FUNCTION order_status_history_no_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'order_status_history is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_FN_SELLER = """
CREATE OR REPLACE FUNCTION seller_order_status_history_no_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'seller_order_status_history is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRG_ORDER = """
CREATE TRIGGER order_status_history_no_mutation_trigger
BEFORE UPDATE OR DELETE ON shop_orderstatushistory
FOR EACH ROW EXECUTE FUNCTION order_status_history_no_mutation();
"""

CREATE_TRG_SELLER = """
CREATE TRIGGER seller_order_status_history_no_mutation_trigger
BEFORE UPDATE OR DELETE ON shop_sellerorderstatushistory
FOR EACH ROW EXECUTE FUNCTION seller_order_status_history_no_mutation();
"""

DROP_FN_ORDER = "DROP FUNCTION IF EXISTS order_status_history_no_mutation();"
DROP_FN_SELLER = "DROP FUNCTION IF EXISTS seller_order_status_history_no_mutation();"
DROP_TRG_ORDER = (
    "DROP TRIGGER IF EXISTS order_status_history_no_mutation_trigger "
    "ON shop_orderstatushistory;"
)
DROP_TRG_SELLER = (
    "DROP TRIGGER IF EXISTS seller_order_status_history_no_mutation_trigger "
    "ON shop_sellerorderstatushistory;"
)


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0002_orders"),
    ]

    operations = [
        migrations.RunSQL(CREATE_FN_ORDER, DROP_FN_ORDER),
        migrations.RunSQL(CREATE_FN_SELLER, DROP_FN_SELLER),
        migrations.RunSQL(CREATE_TRG_ORDER, DROP_TRG_ORDER),
        migrations.RunSQL(CREATE_TRG_SELLER, DROP_TRG_SELLER),
    ]
