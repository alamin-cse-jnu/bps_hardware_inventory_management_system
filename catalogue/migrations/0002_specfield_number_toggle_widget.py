from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the 'number_toggle' widget choice (Number + toggle/segmented chips).

    Also widens ``max_length`` 12 → 20 so the new 13-char value fits (fields.E009).
    """

    dependencies = [
        ("catalogue", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subassetspecfield",
            name="widget",
            field=models.CharField(
                choices=[
                    ("text", "Text box"),
                    ("number", "Number + fixed unit"),
                    ("units", "Number + unit chips"),
                    ("number_toggle", "Number + toggle / segmented chips"),
                    ("select", "Dropdown"),
                    ("toggle", "Toggle / segmented chips"),
                ],
                default="text",
                max_length=20,
            ),
        ),
    ]
