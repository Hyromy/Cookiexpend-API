import project.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_retailer_logo'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='GaleriaItem',
            new_name='GalleryItem',
        ),
        migrations.AlterField(
            model_name='galleryitem',
            name='url',
            field=models.ImageField(upload_to=project.utils.PathGenerator('gallery')),
        ),
    ]
