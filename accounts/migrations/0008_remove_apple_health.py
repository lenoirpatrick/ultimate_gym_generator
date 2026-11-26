"""Retrait du module Apple Santé (issue #168).

L'application `health` n'existe plus : ses migrations ne peuvent donc plus
défaire ses propres tables. Celle-ci s'en charge à sa place, puis retire
l'option « Apple Santé activée » du profil. Sans retour arrière : les données
supprimées ne se reconstituent pas.
"""

from django.db import migrations

#: Tables créées par les migrations de l'ancienne application `health`.
HEALTH_TABLES = (
    "health_activity",
    "health_apikey",
    "health_dailysteps",
    "health_excludedimport",
    "health_weightmeasurement",
)


def drop_health_data(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())
    with connection.cursor() as cursor:
        for table in HEALTH_TABLES:
            if table in existing:
                cursor.execute(f"DROP TABLE {schema_editor.quote_name(table)}")
        # Une trace « health appliquée » resterait sinon dans l'historique des
        # migrations d'une application qui n'existe plus.
        cursor.execute("DELETE FROM django_migrations WHERE app = %s", ["health"])

    # Types de contenu orphelins : leurs permissions et entrées du journal
    # d'administration partent avec eux, en cascade.
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="health").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_corde_a_sauter"),
        # Modèles nécessaires à la cascade de suppression des types de contenu.
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(drop_health_data, migrations.RunPython.noop),
        migrations.RemoveField(model_name="user", name="health_enabled"),
    ]
