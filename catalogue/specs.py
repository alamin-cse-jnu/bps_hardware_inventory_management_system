"""
Helpers that turn ``SubAssetSpecField`` definitions into form data and back.

These keep the asset views thin: one place builds the field list for a Sub Asset,
collects POSTed values into the ``specifications`` JSON, and renders stored values
for display. The storage convention is:

    text / select / toggle / number   -> specifications[key] = "value"
    units (number + unit chips)        -> specifications[key] = {"qty": "...", "unit": "..."}
"""

import re


def slugify_key(label: str) -> str:
    """Turn a human label into a safe storage key, e.g. 'RAM Type' -> 'ram_type'."""
    return re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")


def active_fields(asset_type) -> list:
    """Active SubAssetSpecField rows for a Sub Asset (AssetType), ordered."""
    if asset_type is None:
        return []
    return list(asset_type.spec_fields.filter(is_active=True).order_by("order", "id"))


def field_dicts(asset_type) -> list[dict]:
    """Serialisable field definitions for the form / API."""
    return [f.as_dict() for f in active_fields(asset_type)]


def collect_values(asset_type, post_data) -> dict:
    """Build the specifications dict from POSTed ``spec_<key>`` inputs."""
    specs: dict = {}
    for field in active_fields(asset_type):
        name = f"spec_{field.key}"
        if field.widget == "units":
            qty = post_data.get(name, "").strip()
            unit = post_data.get(f"{name}_unit", "").strip()
            if qty or unit:
                specs[field.key] = {"qty": qty, "unit": unit}
        else:
            val = post_data.get(name, "").strip()
            if val:
                specs[field.key] = val
    return specs


def form_values(asset_type, specifications) -> list[dict]:
    """
    Field definitions merged with the current value, for rendering the form.
    Each item: {**field.as_dict(), "value": <str>, "qty": <str>, "unit": <str>}.
    """
    specifications = specifications or {}
    rows = []
    for field in active_fields(asset_type):
        d = field.as_dict()
        raw = specifications.get(field.key)
        if field.widget == "units":
            raw = raw if isinstance(raw, dict) else {}
            # Chips come from options; fall back to the unit value as a single chip.
            d["options"] = d["options"] or ([field.unit] if field.unit else [])
            d["qty"] = raw.get("qty", "")
            d["unit"] = raw.get("unit", "")  # selected chip
            d["value"] = ""
        else:
            # Keep d["unit"] from the definition so the number widget shows its badge.
            d["value"] = raw if isinstance(raw, str) else ""
            d["qty"] = ""
        rows.append(d)
    return rows


def display_rows(asset_type, specifications) -> list[tuple[str, str]]:
    """(label, formatted value) pairs for the asset detail page."""
    specifications = specifications or {}
    out = []
    for field in active_fields(asset_type):
        raw = specifications.get(field.key)
        if raw in (None, "", {}):
            continue
        if field.widget == "units" and isinstance(raw, dict):
            text = f"{raw.get('qty', '')} {raw.get('unit', '')}".strip()
        elif field.widget == "number" and field.unit:
            text = f"{raw} {field.unit}".strip()
        else:
            text = raw if isinstance(raw, str) else str(raw)
        if text:
            out.append((field.label, text))
    return out
