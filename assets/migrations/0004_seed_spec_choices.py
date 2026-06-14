"""Seed initial SpecChoice values for CPU model, RAM type, storage type, OS name, and GPU fields."""
from django.db import migrations

SEED = [
    # CPU model / series
    ("cpu_model", [
        (0,  "i3",           "Intel Core i3"),
        (1,  "i5",           "Intel Core i5"),
        (2,  "i7",           "Intel Core i7"),
        (3,  "i9",           "Intel Core i9"),
        (4,  "Xeon",         "Intel Xeon"),
        (5,  "Pentium",      "Intel Pentium"),
        (6,  "Celeron",      "Intel Celeron"),
        (7,  "Ryzen 3",      "AMD Ryzen 3"),
        (8,  "Ryzen 5",      "AMD Ryzen 5"),
        (9,  "Ryzen 7",      "AMD Ryzen 7"),
        (10, "Ryzen 9",      "AMD Ryzen 9"),
        (11, "Threadripper", "AMD Threadripper"),
        (12, "Other",        "Other"),
    ]),
    # RAM type
    ("ram_type", [
        (0, "DDR3",   "DDR3"),
        (1, "DDR4",   "DDR4"),
        (2, "DDR5",   "DDR5"),
        (3, "LPDDR4", "LPDDR4"),
        (4, "LPDDR5", "LPDDR5"),
    ]),
    # Storage type
    ("storage_type", [
        (0, "SSD",      "SSD"),
        (1, "HDD",      "HDD"),
        (2, "NVMe SSD", "NVMe SSD"),
        (3, "eMMC",     "eMMC"),
        (4, "Hybrid",   "Hybrid (SSHD)"),
    ]),
    # OS name
    ("os_name", [
        (0, "Windows 11",          "Windows 11"),
        (1, "Windows 10",          "Windows 10"),
        (2, "Windows Server 2022", "Windows Server 2022"),
        (3, "Windows Server 2019", "Windows Server 2019"),
        (4, "Ubuntu 22.04",        "Ubuntu 22.04 LTS"),
        (5, "Ubuntu 24.04",        "Ubuntu 24.04 LTS"),
        (6, "Linux",               "Linux (Other)"),
    ]),
    # GPU chipset
    ("gpu_chipset", [
        (0,  "Integrated",             "Integrated Graphics"),
        (1,  "NVIDIA GeForce GTX 1650","NVIDIA GeForce GTX 1650"),
        (2,  "NVIDIA GeForce GTX 1660","NVIDIA GeForce GTX 1660"),
        (3,  "NVIDIA GeForce RTX 3060","NVIDIA GeForce RTX 3060"),
        (4,  "NVIDIA GeForce RTX 3070","NVIDIA GeForce RTX 3070"),
        (5,  "NVIDIA GeForce RTX 3080","NVIDIA GeForce RTX 3080"),
        (6,  "NVIDIA GeForce RTX 4060","NVIDIA GeForce RTX 4060"),
        (7,  "NVIDIA GeForce RTX 4070","NVIDIA GeForce RTX 4070"),
        (8,  "AMD Radeon RX 6600",     "AMD Radeon RX 6600"),
        (9,  "AMD Radeon RX 6700",     "AMD Radeon RX 6700"),
        (10, "Intel Arc A380",         "Intel Arc A380"),
        (11, "Other",                  "Other"),
    ]),
    # GPU memory type
    ("gpu_memory_type", [
        (0, "Integrated", "Integrated / Shared"),
        (1, "GDDR5",      "GDDR5"),
        (2, "GDDR6",      "GDDR6"),
        (3, "GDDR6X",     "GDDR6X"),
    ]),
    # GPU capacity
    ("gpu_capacity", [
        (0, "Integrated", "Integrated / Shared"),
        (1, "2 GB",       "2 GB"),
        (2, "4 GB",       "4 GB"),
        (3, "6 GB",       "6 GB"),
        (4, "8 GB",       "8 GB"),
        (5, "12 GB",      "12 GB"),
        (6, "16 GB",      "16 GB"),
        (7, "24 GB",      "24 GB"),
    ]),
]


def seed_choices(apps, schema_editor):
    SpecChoice = apps.get_model("assets", "SpecChoice")
    for spec_key, entries in SEED:
        for order, value, label in entries:
            SpecChoice.objects.get_or_create(
                spec_key=spec_key,
                value=value,
                defaults={"label": label, "order": order},
            )


def unseed_choices(apps, schema_editor):
    SpecChoice = apps.get_model("assets", "SpecChoice")
    keys = [k for k, _ in SEED]
    SpecChoice.objects.filter(spec_key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0003_catalog_dropdowns"),
    ]

    operations = [
        migrations.RunPython(seed_choices, reverse_code=unseed_choices),
    ]
