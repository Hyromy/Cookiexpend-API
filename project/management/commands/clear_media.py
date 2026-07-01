import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import FileField, ImageField, Model


class Command(BaseCommand):
    help = "Clear unused media files from the MEDIA_ROOT directory."

    def handle(self, *args, **options):
        self.stdout.write("Clearing media...")

        fields: list[tuple[Model, FileField | ImageField]] = []
        for model in apps.get_models():
            for field in model._meta.get_fields():
                if isinstance(field, (FileField, ImageField)):
                    fields.append((model, field))

        files_db = set()
        for model, field in fields:
            values = model.objects.values_list(field.name, flat=True).exclude(
                **{f"{field.name}": ""}
            )
            for value in values:
                if value:
                    files_db.add(str(value))

        media_root = settings.MEDIA_ROOT
        files_deleted = 0
        free_space = 0

        for root, _, files in os.walk(media_root):
            for file in files:
                path_abs = os.path.join(root, file)
                path_rel = os.path.relpath(path_abs, media_root).replace("\\", "/")

                if path_rel not in files_db:
                    try:
                        file_size = os.path.getsize(path_abs)
                        os.remove(path_abs)

                        self.stdout.write(f"Deleted: {path_rel} ({file_size / 1024:.2f} KB)")
                        files_deleted += 1
                        free_space += file_size

                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f"Error deleting {path_rel}: {e}"))

        if files_deleted > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deleted {files_deleted} files, freeing {free_space / (1024 * 1024):.2f} MB"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("No files to delete."))
