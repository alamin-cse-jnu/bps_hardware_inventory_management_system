from django import template

register = template.Library()

_SPEC_LABELS = {
    "ram": "RAM",
    "storage": "Storage",
    "display": "Display/Monitor",
    "display_monitor": "Display/Monitor",
    "os": "Operating System",
    "cpu": "CPU",
}


@register.filter
def spec_key_label(key):
    return _SPEC_LABELS.get(str(key).lower(), str(key).replace("_", " ").title())


@register.filter
def format_spec_val(value, key=""):
    """Format a spec value for display; handles nested dicts for composite specs."""
    if value is None or value == "" or value == {}:
        return "—"
    if not isinstance(value, dict):
        return str(value)
    key = str(key).lower()
    if key == "ram":
        parts = []
        if value.get("qty"):
            parts.append(f"{value['qty']} GB")
        if value.get("type"):
            parts.append(value["type"])
        return " ".join(parts) or "—"
    elif key == "storage":
        parts = []
        if value.get("qty"):
            parts.append(value["qty"])
        if value.get("unit"):
            parts.append(value["unit"])
        if value.get("type"):
            parts.append(value["type"])
        return " ".join(parts) or "—"
    elif key in ("display", "display_monitor"):
        size = value.get("size", "")
        return f"{size} inches" if size else "—"
    elif key == "os":
        parts = []
        if value.get("name"):
            parts.append(value["name"])
        if value.get("licensed"):
            parts.append(f"[Licensed: {value['licensed']}]")
        return " ".join(parts) or "—"
    elif key == "cpu":
        parts = []
        if value.get("brand"):
            parts.append(value["brand"])
        if value.get("cores"):
            parts.append(f"{value['cores']} cores")
        if value.get("generation"):
            parts.append(value["generation"])
        return " · ".join(parts) or "—"
    # Fallback for unknown composite keys
    return ", ".join(f"{k}: {v}" for k, v in value.items() if v) or "—"
