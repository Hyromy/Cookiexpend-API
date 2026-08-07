from django.db import migrations


def backfill_product_images(apps, schema_editor):
    Product = apps.get_model("store_mgmt", "Product")
    ProductImage = apps.get_model("store_mgmt", "ProductImage")

    for product in Product.all_objects.filter(deleted_at__isnull=True).exclude(img__in=["", None]):
        ProductImage.all_objects.create(product=product, img=product.img.name, order=0)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('store_mgmt', '0017_productimage'),
    ]

    operations = [
        migrations.RunPython(backfill_product_images, noop),
        migrations.RemoveField(
            model_name='product',
            name='img',
        ),
    ]
