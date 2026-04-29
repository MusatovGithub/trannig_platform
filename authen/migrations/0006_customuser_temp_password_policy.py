from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("authen", "0005_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="must_change_password",
            field=models.BooleanField(
                default=False,
                verbose_name="Требуется смена пароля",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="temporary_password_expires_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Срок действия временного пароля",
            ),
        ),
    ]
