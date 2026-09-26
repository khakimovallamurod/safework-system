from django.db import migrations


def add_missing_internal_guideline_columns(apps, schema_editor):
    connection = schema_editor.connection
    columns_by_table = {
        'ichki_nizom': {
            'start_time': 'datetime(6) NULL',
            'registration_end_time': 'datetime(6) NULL',
            'active_until': 'datetime(6) NULL',
        },
        'ichki_nizom_yuborish': {
            'is_active': 'tinyint(1) NOT NULL DEFAULT 0',
            'start_time': 'datetime(6) NULL',
            'registration_end_time': 'datetime(6) NULL',
            'active_until': 'datetime(6) NULL',
        },
    }

    with connection.cursor() as cursor:
        existing_tables = connection.introspection.table_names(cursor)

        for table_name, required_columns in columns_by_table.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, table_name)
            }

            for column_name, definition in required_columns.items():
                if column_name in existing_columns:
                    continue

                cursor.execute(
                    f'ALTER TABLE {schema_editor.quote_name(table_name)} '
                    f'ADD COLUMN {schema_editor.quote_name(column_name)} {definition}'
                )


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            add_missing_internal_guideline_columns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
