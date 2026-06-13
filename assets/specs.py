"""
Single source of truth for the "known" rich specification fields.

``AssetType.spec_schema`` is an ordered list of spec keys. Five keys have
purpose-built widgets on the asset form (see ``templates/assets/partials/
spec_fields.html`` and ``assets/views.py:_collect_specs``); every other key is
rendered as a free-text box. The catalog spec-builder UI uses this registry to
present the known fields as friendly toggles and treats the rest as custom
free-text fields.
"""

import re

# (key, label, description shown in the builder UI)
KNOWN_SPEC_FIELDS: list[tuple[str, str, str]] = [
    ("cpu",     "CPU",                "Brand (Intel / AMD), core count, generation"),
    ("ram",     "RAM",                "Size in GB and DDR generation"),
    ("storage", "Storage",            "Capacity (GB / TB) and SSD / HDD type"),
    ("display", "Display / Monitor",  "Screen size in inches"),
    ("os",      "Operating System",   "OS name and licensing status"),
]

KNOWN_SPEC_KEYS: list[str] = [k for k, _, _ in KNOWN_SPEC_FIELDS]
_KNOWN_LABELS: dict[str, str] = {k: lbl for k, lbl, _ in KNOWN_SPEC_FIELDS}


def slugify_spec_key(label: str) -> str:
    """Turn a human field name into a safe spec key, e.g. 'WiFi Standard' -> 'wifi_standard'."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug


def spec_label(key: str) -> str:
    """Friendly label for any spec key (known label, else title-cased slug)."""
    return _KNOWN_LABELS.get(key, key.replace("_", " ").title())


def split_schema(schema) -> tuple[list[str], list[str]]:
    """Split a stored spec_schema into (known_keys, custom_keys), preserving order."""
    schema = schema or []
    known = [k for k in schema if k in KNOWN_SPEC_KEYS]
    custom = [k for k in schema if k not in KNOWN_SPEC_KEYS]
    return known, custom


def compose_schema(checked_known, custom_labels) -> list[str]:
    """
    Build an ordered, de-duplicated spec_schema from builder input:
    known fields in registry order first, then custom fields in entry order.
    """
    checked = set(checked_known or [])
    result = [k for k in KNOWN_SPEC_KEYS if k in checked]

    seen = set(result)
    for raw in custom_labels or []:
        key = slugify_spec_key(raw)
        if key and key not in seen:
            result.append(key)
            seen.add(key)
    return result
