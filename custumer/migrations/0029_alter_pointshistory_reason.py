from django.db import migrations, models

import custumer.schemas


class Migration(migrations.Migration):
    dependencies = [
        ("custumer", "0028_custumersubscriptonpayment_idx_payment_attendance_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pointshistory",
            name="reason",
            field=models.CharField(
                choices=custumer.schemas.ReasonTextChoices.choices,
                max_length=50,
                verbose_name="Причина",
            ),
        ),
    ]
