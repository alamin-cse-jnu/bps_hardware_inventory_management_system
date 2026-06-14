"""
Advanced specification filters & formatters for the Current Inventory report.

Asset ``specifications`` is a JSONField whose composite keys are saved as nested
dicts by the asset form (see ``assets/views.py:_collect_specs``)::

    cpu     -> {"brand", "cores", "generation"}
    ram     -> {"qty" (GB), "type"}
    storage -> {"qty", "unit" ("GB"/"TB"), "type"}
    display -> {"size" (inches)}          (legacy key: "display_monitor")
    os      -> {"name", "licensed"}

Numeric values are stored as *strings*, and legacy / Excel-imported rows may hold
a plain string instead of a dict. Every extraction below is therefore defensive,
and all numeric range filtering happens in Python rather than via unreliable
JSON range queries against quoted string values.
"""

import re

CPU_BRANDS = ["Intel", "AMD"]
RAM_TYPES = ["DDR3", "DDR4", "DDR5"]
STORAGE_TYPES = ["SSD", "HDD", "NVMe", "eMMC"]
CORE_OPS = [("gte", "≥"), ("eq", "="), ("lte", "≤")]  # >=, =, <=


# ── Value extraction ───────────────────────────────────────────────────────────

def _to_number(value):
    """Best-effort numeric parse of a spec value; None if no number is present."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group()) if m else None


def _sub(specs, key):
    """Return the nested spec dict for ``key`` (empty dict if missing/not a dict)."""
    val = specs.get(key) if isinstance(specs, dict) else None
    return val if isinstance(val, dict) else {}


def cpu_brand(specs):
    return str(_sub(specs, "cpu").get("brand", "")).strip()


def cpu_cores(specs):
    return _to_number(_sub(specs, "cpu").get("cores"))


def ram_gb(specs):
    return _to_number(_sub(specs, "ram").get("qty"))


def storage_gb(specs):
    d = _sub(specs, "storage")
    qty = _to_number(d.get("qty"))
    if qty is None:
        return None
    unit = str(d.get("unit", "GB")).strip().upper()
    return qty * 1024 if unit == "TB" else qty


def storage_type(specs):
    return str(_sub(specs, "storage").get("type", "")).strip()


def display_inches(specs):
    d = _sub(specs, "display") or _sub(specs, "display_monitor")
    return _to_number(d.get("size"))


# ── Display formatters (for table cells / Excel / PDF) ──────────────────────────

def fmt_ram(specs):
    d = _sub(specs, "ram")
    parts = []
    if d.get("qty"):
        parts.append(f"{d['qty']} GB")
    if d.get("type"):
        parts.append(str(d["type"]))
    return " ".join(parts)


def fmt_storage(specs):
    d = _sub(specs, "storage")
    parts = []
    if d.get("qty"):
        parts.append(str(d["qty"]))
    if d.get("unit"):
        parts.append(str(d["unit"]))
    if d.get("type"):
        parts.append(str(d["type"]))
    return " ".join(parts)


def fmt_display(specs):
    size = (_sub(specs, "display") or _sub(specs, "display_monitor")).get("size", "")
    return f'{size}"' if size else ""


def fmt_gpu(specs):
    d = _sub(specs, "gpu")
    parts = []
    if d.get("chipset"):
        parts.append(str(d["chipset"]))
    if d.get("memory_type"):
        parts.append(str(d["memory_type"]))
    if d.get("capacity"):
        parts.append(str(d["capacity"]))
    return " · ".join(parts)


def fmt_cpu(specs):  # updated to include model
    d = _sub(specs, "cpu")
    parts = []
    if d.get("brand"):
        parts.append(str(d["brand"]))
    if d.get("model"):
        parts.append(str(d["model"]))
    if d.get("cores"):
        parts.append(f"{d['cores']} cores")
    if d.get("generation"):
        parts.append(str(d["generation"]))
    return " · ".join(parts)


# ── Filter parsing & application ────────────────────────────────────────────────

def parse_spec_filters(get):
    """Extract advanced spec-filter params from a request.GET (or plain dict)."""
    def g(name):
        return (get.get(name) or "").strip()

    op = g("cores_op")
    # Storage range is entered in the user-selected unit; normalise to GB so the
    # matcher (which works in GB) stays unit-agnostic.
    s_mult = 1024 if g("storage_unit").upper() == "TB" else 1
    s_min = _to_number(g("storage_min"))
    s_max = _to_number(g("storage_max"))
    return {
        "cpu_brand":    g("cpu_brand"),
        "cores_op":     op if op in dict(CORE_OPS) else "",
        "cores_val":    _to_number(g("cores_val")),
        "ram_min":      _to_number(g("ram_min")),
        "ram_max":      _to_number(g("ram_max")),
        "storage_type": g("storage_type"),
        "storage_min":  s_min * s_mult if s_min is not None else None,
        "storage_max":  s_max * s_mult if s_max is not None else None,
        "display_min":  _to_number(g("display_min")),
        "display_max":  _to_number(g("display_max")),
    }


def is_active(f) -> bool:
    """True when at least one advanced spec filter carries a usable value."""
    return any((
        f["cpu_brand"],
        f["cores_op"] and f["cores_val"] is not None,
        f["ram_min"] is not None,
        f["ram_max"] is not None,
        f["storage_type"],
        f["storage_min"] is not None,
        f["storage_max"] is not None,
        f["display_min"] is not None,
        f["display_max"] is not None,
    ))


def _matches(asset, f) -> bool:
    specs = asset.specifications or {}

    if f["cpu_brand"] and f["cpu_brand"].lower() not in cpu_brand(specs).lower():
        return False

    if f["cores_op"] and f["cores_val"] is not None:
        c = cpu_cores(specs)
        if c is None:
            return False
        op, target = f["cores_op"], f["cores_val"]
        if op == "gte" and not c >= target:
            return False
        if op == "lte" and not c <= target:
            return False
        if op == "eq" and c != target:
            return False

    if f["ram_min"] is not None or f["ram_max"] is not None:
        r = ram_gb(specs)
        if r is None:
            return False
        if f["ram_min"] is not None and r < f["ram_min"]:
            return False
        if f["ram_max"] is not None and r > f["ram_max"]:
            return False

    if f["storage_type"] and f["storage_type"].lower() not in storage_type(specs).lower():
        return False

    if f["storage_min"] is not None or f["storage_max"] is not None:
        s = storage_gb(specs)
        if s is None:
            return False
        if f["storage_min"] is not None and s < f["storage_min"]:
            return False
        if f["storage_max"] is not None and s > f["storage_max"]:
            return False

    if f["display_min"] is not None or f["display_max"] is not None:
        d = display_inches(specs)
        if d is None:
            return False
        if f["display_min"] is not None and d < f["display_min"]:
            return False
        if f["display_max"] is not None and d > f["display_max"]:
            return False

    return True


def filter_assets(assets, f):
    """Filter an iterable of AssetItem by the parsed advanced spec filters."""
    if not is_active(f):
        return list(assets)
    return [a for a in assets if _matches(a, f)]
