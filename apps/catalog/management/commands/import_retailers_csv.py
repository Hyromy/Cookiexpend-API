import csv
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.catalog.models import Brand, Retailer


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def get(row, key):
    return (row.get(key) or "").strip()


def common_word_prefix(names):
    word_lists = [name.split() for name in names]
    shortest = min(len(w) for w in word_lists)
    prefix = []
    for i in range(shortest):
        candidate = word_lists[0][i]
        if all(w[i].lower() == candidate.lower() for w in word_lists):
            prefix.append(candidate)
        else:
            break
    return " ".join(prefix)


class Command(BaseCommand):
    help = "Import Retailer/Brand records from a contacts CSV export, grouping stores into brands by shared RFC."

    def add_arguments(self, parser):
        parser.add_argument("--contacts", required=True)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created/updated without touching the database.",
        )

    def handle(self, *args, **options):
        rows = read_csv(options["contacts"])
        dry_run = options["dry_run"]

        complete = []
        skipped = 0
        for row in rows:
            name = get(row, "Name*")
            street = get(row, "Street")
            street2 = get(row, "Street2")
            city = get(row, "City")
            state = get(row, "State")
            rfc = get(row, "Numero de identificación fiscal")

            if not (name and street and city and state):
                skipped += 1
                continue

            address = f"{street}, {street2}" if street2 else street
            complete.append(
                {"name": name, "address": address, "state": state, "municipality": city, "rfc": rfc}
            )

        by_rfc = defaultdict(list)
        for row in complete:
            by_rfc[row["rfc"]].append(row)

        brands_created = brands_reused = 0
        retailers_created = retailers_updated = 0

        for rfc, members in by_rfc.items():
            brand = None
            brand_name = None
            if len(members) > 1:
                brand_name = common_word_prefix([m["name"] for m in members]) or members[0]["name"]
                if dry_run:
                    self.stdout.write(f"[Brand] '{brand_name}' <- {len(members)} retailers (RFC {rfc})")
                else:
                    brand, created = Brand.objects.get_or_create(name=brand_name)
                    brands_created += created
                    brands_reused += not created

            for m in members:
                if dry_run:
                    self.stdout.write(
                        f"  [Retailer] {m['name']} | {m['address']} | {m['municipality']}, {m['state']} | brand={brand_name}"
                    )
                    continue

                _retailer, created = Retailer.objects.update_or_create(
                    name=m["name"],
                    defaults={
                        "address": m["address"],
                        "state": m["state"],
                        "municipality": m["municipality"],
                        "brand": brand,
                    },
                )
                retailers_created += created
                retailers_updated += not created

        self.stdout.write(self.style.SUCCESS(f"Skipped {skipped} rows without a complete address"))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes were made"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Brands: {brands_created} created, {brands_reused} reused | "
                    f"Retailers: {retailers_created} created, {retailers_updated} updated"
                )
            )
