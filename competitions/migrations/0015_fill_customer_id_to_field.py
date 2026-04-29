from django.db import migrations


def fill_customer_profile(apps, schema_editor):
    Result = apps.get_model("competitions", "CustumerCompetitionResult")
    Custumer = apps.get_model("custumer", "Custumer")

    user_to_customer = dict(
        Custumer.objects.filter(user_id__isnull=False).values_list(
            "user_id", "id"
        )
    )

    for result in Result.objects.all().iterator():
        target_id = user_to_customer.get(result.custumer_id)
        if target_id:
            Result.objects.filter(pk=result.pk).update(customer_id=target_id)
        else:
            # решите, что делать: удалить? создать заглушку? пропустить?
            Result.objects.filter(pk=result.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "competitions",
            "0014_custumercompetitionresult_customer_id_and_more",
        ),
        ("custumer", "0025_alter_custumersubscriptonpayment_is_blok_and_more"),
    ]

    operations = [
        migrations.RunPython(fill_customer_profile, migrations.RunPython.noop),
    ]
