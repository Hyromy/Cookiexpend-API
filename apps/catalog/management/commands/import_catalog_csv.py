import csv
import json
import os
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import Category, Presentation
from apps.store_mgmt.models import Product

# Category CSV `id` -> logo file already present in media/categories/, matched by
# viewing each image (opaque upload tokens carry no category info on their own).
CATEGORY_LOGOS = {
    "banderilla": "20260706_bc2be700.png",
    "barra-coco": "20260706_4450503e.png",
    "barra-nuez": "20260706_7348294f.png",
    "chispa": "20260706_75b717df.png",
    "estrella": "20260706_d0d55e91.png",
    "oreja": "20260706_d4f20b28.png",
    "polvoron": "20260706_92a9c23d.png",
    "rellena": "20260706_82572890.png",
    "surtido": "20260706_3419be9b.png",
    "tartaleta": "20260706_4c833936.png",
    "trigoleta": "20260706_9e217d56.png",
}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


class Command(BaseCommand):
    help = "Import categorias/presentaciones/productos CSVs (Supabase export) into the local catalog."

    def add_arguments(self, parser):
        parser.add_argument("--categorias", required=True)
        parser.add_argument("--presentaciones", required=True)
        parser.add_argument("--productos", required=True)
        parser.add_argument(
            "--price",
            default="0.01",
            help="Placeholder price applied to every imported product (CSV has no price column).",
        )

    def handle(self, *args, **options):
        price = Decimal(options["price"])

        category_label_by_id = self._import_categorias(options["categorias"])
        presentation_label_by_id = self._import_presentaciones(options["presentaciones"])
        self._import_productos(
            options["productos"], category_label_by_id, presentation_label_by_id, price
        )

    def _import_categorias(self, path):
        label_by_id = {}
        created_count = updated_count = 0

        for row in read_csv(path):
            cid = row["id"].strip()
            label = row["label"].strip()
            order = int(row["orden"] or 0)
            label_by_id[cid] = label

            category, created = Category.objects.update_or_create(
                label=label, defaults={"order": order}
            )
            created_count += created
            updated_count += not created

            logo_filename = CATEGORY_LOGOS.get(cid)
            if logo_filename and not category.logo:
                logo_path = os.path.join(settings.MEDIA_ROOT, "categories", logo_filename)
                if os.path.exists(logo_path):
                    category.logo.name = f"categories/{logo_filename}"
                    category.save(update_fields=["logo"])
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Logo file not found for '{label}': {logo_path}")
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Categorias: {created_count} created, {updated_count} updated")
        )
        return label_by_id

    def _import_presentaciones(self, path):
        label_by_id = {}
        created_count = updated_count = 0

        for row in read_csv(path):
            pid = row["id"].strip()
            label = row["label"].strip()
            order = int(row["orden"] or 0)
            label_by_id[pid] = label

            _presentation, created = Presentation.objects.update_or_create(
                label=label, defaults={"order": order}
            )
            created_count += created
            updated_count += not created

        self.stdout.write(
            self.style.SUCCESS(
                f"Presentaciones: {created_count} created, {updated_count} updated"
            )
        )
        return label_by_id

    def _import_productos(self, path, category_label_by_id, presentation_label_by_id, price):
        rows = read_csv(path)

        category_by_label = {c.label: c for c in Category.objects.all()}
        presentation_by_label = {p.label: p for p in Presentation.objects.all()}

        products_by_sku = {}
        created_count = updated_count = 0

        for row in rows:
            sku = row["id"].strip()
            category_id = (row.get("category") or "").strip()
            presentation_id = (row.get("presentacion") or "").strip()

            category = None
            if category_id:
                label = category_label_by_id.get(category_id)
                category = category_by_label.get(label) if label else None
                if category is None:
                    self.stdout.write(
                        self.style.WARNING(f"[{sku}] unknown category id '{category_id}'")
                    )

            presentation = None
            if presentation_id:
                label = presentation_label_by_id.get(presentation_id)
                presentation = presentation_by_label.get(label) if label else None
                if presentation is None:
                    self.stdout.write(
                        self.style.WARNING(f"[{sku}] unknown presentacion id '{presentation_id}'")
                    )

            product, created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": row["name"].strip(),
                    "slug": row["slug"].strip(),
                    "description": (row.get("description") or "").strip(),
                    "badge": (row.get("badge") or "").strip(),
                    "price": price,
                    "category": category,
                    "presentation": presentation,
                },
            )
            created_count += created
            updated_count += not created

            activo = (row.get("activo") or "true").strip().lower() == "true"
            if not activo and product.deleted_at is None:
                product.deleted_at = timezone.now()
                product.save(update_fields=["deleted_at"])
            elif activo and product.deleted_at is not None:
                product.deleted_at = None
                product.save(update_fields=["deleted_at"])

            products_by_sku[sku] = (product, row)

        for sku, (product, row) in products_by_sku.items():
            variantes_raw = (row.get("variantes") or "").strip()
            if not variantes_raw:
                continue

            try:
                variant_skus = json.loads(variantes_raw)
            except json.JSONDecodeError:
                raise CommandError(f"[{sku}] invalid variantes JSON: {variantes_raw!r}")

            for variant_sku in variant_skus:
                variant = products_by_sku.get(variant_sku)
                if variant is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{sku}] variant sku '{variant_sku}' not found among imported products"
                        )
                    )
                    continue
                product.variants.add(variant[0])

        self.stdout.write(
            self.style.SUCCESS(f"Productos: {created_count} created, {updated_count} updated")
        )
