from django.db import migrations


def seed_groups_and_payment_methods(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    PaymentMethod = apps.get_model("store_mgmt", "PaymentMethod")

    for name in ["Factory manager", "Store manager"]:
        Group.objects.get_or_create(name=name)

    existing = PaymentMethod.all_objects.filter(name="cash").first()
    if existing is None:
        PaymentMethod.all_objects.create(name="cash")
    elif existing.deleted_at is not None:
        PaymentMethod.all_objects.filter(pk=existing.pk).update(deleted_at=None)


def unseed_groups_and_payment_methods(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    PaymentMethod = apps.get_model("store_mgmt", "PaymentMethod")

    Group.objects.filter(name__in=["Factory manager", "Store manager"]).delete()
    PaymentMethod.all_objects.filter(name="cash").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("store_mgmt", "0002_establishment_sell_remove_product_description_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(seed_groups_and_payment_methods, unseed_groups_and_payment_methods),
    ]
