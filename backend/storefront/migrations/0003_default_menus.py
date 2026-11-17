from django.db import migrations

NAV = [("Shop", "#catalog"), ("Ritual", "#ritual"), ("For Business", "#business")]
FOOTER = [
    ("Shop", "categories", []),
    ("Business", "links", [
        ("Wholesale enquiry", "enquire:retailer", "store"),
        ("Hotel amenity kits", "enquire:hotel", "hotel"),
        ("Corporate gifting", "enquire:corporate", "gift"),
        ("Contact us", "enquire", "mail"),
    ]),
    ("Talk to us", "contact", []),
]


def create_defaults(apps, schema_editor):
    NavLink = apps.get_model("storefront", "NavLink")
    FooterColumn = apps.get_model("storefront", "FooterColumn")
    FooterLink = apps.get_model("storefront", "FooterLink")
    if not NavLink.objects.exists():
        for i, (label, link) in enumerate(NAV):
            NavLink.objects.create(label=label, link=link, order=i)
    if not FooterColumn.objects.exists():
        for i, (title, kind, links) in enumerate(FOOTER):
            col = FooterColumn.objects.create(title=title, kind=kind, order=i)
            for j, (label, link, icon) in enumerate(links):
                FooterLink.objects.create(column=col, label=label, link=link, icon=icon, order=j)


class Migration(migrations.Migration):
    dependencies = [("storefront", "0002_design_studio")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
