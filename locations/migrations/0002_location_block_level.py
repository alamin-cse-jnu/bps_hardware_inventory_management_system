from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the BLOCK level to Location.level_type choices.

    Choices are validation-level only for a CharField, so this does not alter
    the database column and touches no existing rows. The Floor→Room rows are
    re-parented separately by the gated ``migrate_location_blocks`` command.
    """

    dependencies = [
        ("locations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="location",
            name="level_type",
            field=models.CharField(
                choices=[
                    ("BUILDING", "Building"),
                    ("FLOOR", "Floor"),
                    ("BLOCK", "Block"),
                    ("ROOM", "Room"),
                ],
                max_length=10,
            ),
        ),
    ]
