from django.db import migrations


def add_missing_personnel_columns(apps, schema_editor):
    Personnel = apps.get_model("cards", "Personnel")
    table_name = Personnel._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    existing_columns = {col.name for col in description}

    target_fields = [
        "sex",
        "date_of_birth",
        "place_of_birth",
        "nationality",
        "marital_status",
        "current_address",
        "phone",
        "email",
        "category_other",
        "function_quality",
        "grade",
        "assignment_service",
        "contract_type",
        "contract_reference",
        "service_start_date",
        "identity_photo_physical",
        "identity_photo_digital",
        "contract_copy_attached",
        "other_pieces_attached",
        "other_pieces_details",
        "contract_file",
        "other_pieces_file",
        "engagement_confirmed",
        "place_signed",
        "signature_date",
        "name_signature",
        "admin_received_by",
        "admin_function",
        "admin_received_date",
        "admin_observations",
        "admin_signature_stamp",
    ]

    for field_name in target_fields:
        if field_name in existing_columns:
            continue
        field = Personnel._meta.get_field(field_name)
        schema_editor.add_field(Personnel, field)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("cards", "0012_personnel_admin_function_and_more"),
    ]

    operations = [
        migrations.RunPython(add_missing_personnel_columns, migrations.RunPython.noop),
    ]

