from django.db import migrations


class Migration(migrations.Migration):
    """
    Converts the public_token column from char(32) (created by older Django/MySQL
    migrations) to the native MariaDB uuid type, which Django 6.0 requires when
    running on MariaDB >= 10.7 (has_native_uuid_field=True).

    Without this, Django sends a uuid.UUID object to the driver which gets
    stringified as a 36-char hyphenated string, exceeding char(32).
    """

    dependencies = [
        ("cards", "0013_backfill_missing_personnel_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE cards_card MODIFY COLUMN public_token uuid NOT NULL;",
            reverse_sql="ALTER TABLE cards_card MODIFY COLUMN public_token char(32) NOT NULL;",
        ),
    ]
