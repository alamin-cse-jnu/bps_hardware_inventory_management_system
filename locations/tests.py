from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Block, Building, Level, Location


def make_dims():
    return (
        Building.objects.create(name="Main Building"),
        Block.objects.create(name="South Block"),
        Level.objects.create(name="Level-2"),
    )


def make_location(name="Server Room", **kwargs) -> Location:
    loc = Location(name=name, **kwargs)
    loc.full_clean()
    loc.save()
    return loc


class LocationValidCreationTests(TestCase):
    def setUp(self):
        self.building, self.block, self.level = make_dims()

    def test_location_with_building_only(self):
        loc = make_location(building=self.building)
        self.assertEqual(loc.building, self.building)
        self.assertIsNone(loc.block)
        self.assertIsNone(loc.level)

    def test_location_with_block_only(self):
        loc = make_location(block=self.block)
        self.assertEqual(loc.block, self.block)

    def test_location_with_level_only(self):
        loc = make_location(level=self.level)
        self.assertEqual(loc.level, self.level)

    def test_location_with_all_dimensions_and_room(self):
        loc = make_location(
            building=self.building, block=self.block, level=self.level, room="101"
        )
        self.assertEqual(loc.room, "101")


class LocationValidationErrorTests(TestCase):
    def setUp(self):
        self.building, self.block, self.level = make_dims()

    def test_no_dimension_is_invalid(self):
        loc = Location(name="Nowhere")
        with self.assertRaises(ValidationError):
            loc.full_clean()

    def test_blank_name_is_invalid(self):
        loc = Location(name="  ", building=self.building)
        with self.assertRaises(ValidationError) as ctx:
            loc.full_clean()
        self.assertIn("name", ctx.exception.message_dict)


class LocationLabelTests(TestCase):
    def setUp(self):
        self.building = Building.objects.create(name="Main Building")
        self.block = Block.objects.create(name="South Block")
        self.level = Level.objects.create(name="Level-2")

    def test_descriptor_orders_building_level_block_room(self):
        loc = make_location(
            name="NOC", building=self.building, block=self.block,
            level=self.level, room="301",
        )
        self.assertEqual(
            loc.descriptor, "Main Building · Level-2 · South Block · Room 301"
        )

    def test_full_path_combines_name_and_descriptor(self):
        loc = make_location(name="NOC", building=self.building)
        self.assertEqual(loc.full_path, "NOC — Main Building")

    def test_full_path_is_just_name_when_no_descriptor(self):
        # Note: a location always has ≥1 dimension via clean(), but full_path
        # must still degrade gracefully.
        loc = Location(name="Bare")
        self.assertEqual(loc.full_path, "Bare")

    def test_str_delegates_to_full_path(self):
        loc = make_location(name="NOC", level=self.level)
        self.assertEqual(str(loc), "NOC — Level-2")


class DimensionUniquenessTests(TestCase):
    def test_building_name_unique(self):
        Building.objects.create(name="Main Building")
        dup = Building(name="Main Building")
        with self.assertRaises(ValidationError):
            dup.full_clean()
