import csv
from urllib.request import urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import FAQ, Department, GalleryItem, Subject


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class Command(BaseCommand):
    help = "Import galeria/faqs/departamentos/asuntos CSVs (Supabase export) into the local catalog."

    def add_arguments(self, parser):
        parser.add_argument("--galeria", required=True)
        parser.add_argument("--faqs", required=True)
        parser.add_argument("--departamentos", required=True)
        parser.add_argument("--asuntos", required=True)

    def handle(self, *args, **options):
        self._import_galeria(options["galeria"])
        self._import_faqs(options["faqs"])
        department_by_csv_id = self._import_departamentos(options["departamentos"])
        self._import_asuntos(options["asuntos"], department_by_csv_id)

    def _import_galeria(self, path):
        created_count = updated_count = 0

        for row in read_csv(path):
            alt = row["alt"].strip()
            order = int(row["orden"] or 0)
            url = row["url"].strip()

            item, created = GalleryItem.objects.update_or_create(
                alt=alt, defaults={"order": order}
            )
            created_count += created
            updated_count += not created

            if created or not item.url:
                with urlopen(url) as resp:
                    content = resp.read()
                filename = url.rsplit("/", 1)[-1]
                item.url.save(filename, ContentFile(content), save=True)

        self.stdout.write(
            self.style.SUCCESS(f"Galeria: {created_count} created, {updated_count} updated")
        )

    def _import_faqs(self, path):
        created_count = updated_count = 0

        for row in read_csv(path):
            question = row["pregunta"].strip()
            answer = row["respuesta"].strip()
            order = int(row["orden"] or 0)
            activo = (row.get("activo") or "true").strip().lower() == "true"

            faq, created = FAQ.objects.update_or_create(
                question=question, defaults={"answer": answer, "order": order}
            )
            created_count += created
            updated_count += not created

            self._sync_active(faq, activo)

        self.stdout.write(
            self.style.SUCCESS(f"FAQs: {created_count} created, {updated_count} updated")
        )

    def _import_departamentos(self, path):
        csv_id_to_department = {}
        created_count = updated_count = 0

        for row in read_csv(path):
            csv_id = row["id"].strip()
            name = row["nombre"].strip()
            email = (row.get("email") or "").strip()
            order = int(row["orden"] or 0)
            activo = (row.get("activo") or "true").strip().lower() == "true"

            department, created = Department.objects.update_or_create(
                name=name, defaults={"email": email, "order": order}
            )
            created_count += created
            updated_count += not created

            self._sync_active(department, activo)
            csv_id_to_department[csv_id] = department

        self.stdout.write(
            self.style.SUCCESS(
                f"Departamentos: {created_count} created, {updated_count} updated"
            )
        )
        return csv_id_to_department

    def _import_asuntos(self, path, department_by_csv_id):
        created_count = updated_count = 0

        for row in read_csv(path):
            departamento_id = row["departamento_id"].strip()
            label = row["asunto"].strip()
            order = int(row["orden"] or 0)

            department = department_by_csv_id.get(departamento_id)
            if department is None:
                self.stdout.write(
                    self.style.WARNING(f"[{label}] unknown departamento_id '{departamento_id}'")
                )
                continue

            _subject, created = Subject.objects.update_or_create(
                department=department, label=label, defaults={"order": order}
            )
            created_count += created
            updated_count += not created

        self.stdout.write(
            self.style.SUCCESS(f"Asuntos: {created_count} created, {updated_count} updated")
        )

    def _sync_active(self, instance, activo):
        if not activo and instance.deleted_at is None:
            instance.deleted_at = timezone.now()
            instance.save(update_fields=["deleted_at"])
        elif activo and instance.deleted_at is not None:
            instance.deleted_at = None
            instance.save(update_fields=["deleted_at"])
