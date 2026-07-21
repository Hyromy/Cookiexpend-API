from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('store_mgmt', '0013_product_badge_product_category_product_description_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='variantes',
            new_name='variants',
        ),
    ]
