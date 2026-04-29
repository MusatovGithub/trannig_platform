# competitions/migrations/0021_add_partial_unique_index.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        (
            "competitions",
            "0020_alter_custumercompetitionresult_unique_together_and_more",
        ),
    ]

    operations = [
        # Шаг 1: Убираем unique_together (он конфликтует с дубликатами)
        migrations.AlterUniqueTogether(
            name="custumercompetitionresult",
            unique_together=set(),
        ),
        # Шаг 2: Создаем частичный уникальный индекс через SQL
        # Этот индекс будет применяться только к записям с result_time_ms IS NOT NULL
        migrations.RunSQL(
            # Создаем частичный уникальный индекс только для записей с result_time_ms IS NOT NULL
            sql="""
                CREATE UNIQUE INDEX competitions_result_unique_with_time
                ON competitions_custumercompetitionresult
                (competition_id, customer_id, distance, style, discipline, result_time_ms)
                WHERE result_time_ms IS NOT NULL;
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS competitions_result_unique_with_time;
            """,
        ),
    ]
