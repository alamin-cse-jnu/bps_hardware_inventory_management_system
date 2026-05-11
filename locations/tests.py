from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Location


def make_building(name="Parliament Bhaban") -> Location:
    loc = Location(name=name, level_type=Location.LevelType.BUILDING)
    loc.full_clean()
    loc.save()
    return loc


def make_floor(building: Location, name="3rd Floor") -> Location:
    loc = Location(name=name, level_type=Location.LevelType.FLOOR, parent=building)
    loc.full_clean()
    loc.save()
    return loc


def make_room(floor: Location, name="NOC Room") -> Location:
    loc = Location(name=name, level_type=Location.LevelType.ROOM, parent=floor)
    loc.full_clean()
    loc.save()
    return loc


class LocationValidCreationTests(TestCase):
    def test_building_created_without_parent(self):
        building = make_building()
        self.assertEqual(building.level_type, Location.LevelType.BUILDING)
        self.assertIsNone(building.parent)

    def test_floor_created_under_building(self):
        building = make_building()
        floor = make_floor(building)
        self.assertEqual(floor.parent, building)

    def test_room_created_under_floor(self):
        building = make_building()
        floor = make_floor(building)
        room = make_room(floor)
        self.assertEqual(room.parent, floor)

    def test_floor_without_room_is_valid(self):
        """A floor-level location with no children rooms is perfectly valid."""
        building = make_building()
        floor = make_floor(building, name="Ground Floor")
        self.assertIsNotNone(floor.pk)
        self.assertEqual(floor.parent, building)


class LocationValidationErrorTests(TestCase):
    def test_building_with_parent_is_invalid(self):
        building = make_building("Main Building")
        child_building = Location(
            name="Annex",
            level_type=Location.LevelType.BUILDING,
            parent=building,
        )
        with self.assertRaises(ValidationError) as ctx:
            child_building.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_floor_without_parent_is_invalid(self):
        floor = Location(name="1st Floor", level_type=Location.LevelType.FLOOR)
        with self.assertRaises(ValidationError) as ctx:
            floor.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_floor_under_floor_is_invalid(self):
        building = make_building()
        floor = make_floor(building)
        nested = Location(
            name="Sub-Floor",
            level_type=Location.LevelType.FLOOR,
            parent=floor,
        )
        with self.assertRaises(ValidationError) as ctx:
            nested.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_room_without_parent_is_invalid(self):
        room = Location(name="Server Room", level_type=Location.LevelType.ROOM)
        with self.assertRaises(ValidationError) as ctx:
            room.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_room_under_building_is_invalid(self):
        building = make_building()
        room = Location(
            name="Lobby",
            level_type=Location.LevelType.ROOM,
            parent=building,
        )
        with self.assertRaises(ValidationError) as ctx:
            room.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)


class LocationFullPathTests(TestCase):
    def setUp(self):
        self.building = make_building("Parliament Bhaban")
        self.floor = make_floor(self.building, "3rd Floor")
        self.room = make_room(self.floor, "NOC Room")

    def test_building_full_path(self):
        self.assertEqual(self.building.full_path, "Parliament Bhaban")

    def test_floor_full_path(self):
        self.assertEqual(self.floor.full_path, "Parliament Bhaban → 3rd Floor")

    def test_room_full_path(self):
        self.assertEqual(
            self.room.full_path, "Parliament Bhaban → 3rd Floor → NOC Room"
        )

    def test_floor_only_location_str(self):
        """__str__ delegates to full_path; floor-only shows two parts."""
        self.assertEqual(str(self.floor), "Parliament Bhaban → 3rd Floor")
