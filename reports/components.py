"""
Component Purchases report (Phase 13).

One query layer shared by the view page, the Excel workbook and the PDF, so the
three cannot disagree about what a filter means or what a total is — the same
mistake the office-assets report avoided by centralising ``scope_terms``.

``basis`` decides which date the range applies to:

* ``purchase``  — ``purchase_date``, what was bought in the period. This is the
  procurement question and the default.
* ``installed`` — ``created_at``, what was fitted in the period. A part bought
  from stock months earlier is fitted later, so the two genuinely differ.

Rows carrying no purchase date drop out of a purchase-basis date range — they
have no date to fall inside one. They are still counted when no range is given.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch

from assets.models import AssetComponent

# Report-wide row cap, matching the Transfer Log and Lifecycle views.
ROW_CAP = 5000

BASIS_CHOICES = [
    ("purchase", "Purchase date"),
    ("installed", "Installed date"),
]

STATUS_CHOICES = [
    ("installed", "Currently installed"),
    ("removed", "Removed"),
]

GROUP_CHOICES = [
    ("month", "Month"),
    ("day", "Day"),
]


def _basis_field(basis: str) -> str:
    return "created_at" if basis == "installed" else "purchase_date"


def component_queryset(
    *,
    date_from=None,
    date_to=None,
    basis: str = "purchase",
    vendor_ids: list[int] | None = None,
    ctype_ids: list[int] | None = None,
    status: str = "",
):
    """Filtered component rows, newest purchase first, ready for ``row_dicts``."""
    from assignments.models import Assignment

    qs = (
        AssetComponent.objects.select_related(
            "ctype", "vendor", "parent_asset__asset_type__category",
        )
        .prefetch_related(
            # Current holder of the host asset — one query for the whole page
            # rather than one per row.
            Prefetch(
                "parent_asset__assignments",
                queryset=Assignment.objects.filter(returned_at__isnull=True).select_related(
                    "assignee__employee", "assignee__mp",
                    "assignee__office", "assignee__location",
                ),
                to_attr="active_assignments",
            ),
            # Who fitted the part: the lifecycle event that introduced it.
            Prefetch(
                "swap_events",
                queryset=_add_events(),
                to_attr="add_events",
            ),
        )
        .order_by("-purchase_date", "-created_at", "-id")
    )

    if status == "installed":
        qs = qs.filter(is_active=True)
    elif status == "removed":
        qs = qs.filter(is_active=False)

    field = _basis_field(basis)
    lookup = f"{field}__date" if field == "created_at" else field
    if date_from:
        qs = qs.filter(**{f"{lookup}__gte": date_from})
    if date_to:
        qs = qs.filter(**{f"{lookup}__lte": date_to})

    if vendor_ids:
        qs = qs.filter(vendor_id__in=vendor_ids)
    if ctype_ids:
        qs = qs.filter(ctype_id__in=ctype_ids)

    return qs


def _add_events():
    from lifecycle.models import EventType, LifecycleEvent

    return (
        LifecycleEvent.objects.filter(
            event_type__in=[EventType.COMPONENT_ADD, EventType.COMPONENT_SWAP]
        )
        .select_related("performed_by")
        .order_by("occurred_at")
    )


def _holder(component) -> str:
    active = getattr(component.parent_asset, "active_assignments", None) or []
    return active[0].assignee.display_name if active else ""


def _added_by(component) -> str:
    events = getattr(component, "add_events", None) or []
    if not events:
        return ""
    user = events[0].performed_by
    return user.get_full_name() or user.username


def row_dicts(components, *, date_str, dt_str, detail_url) -> list[dict]:
    """
    Render component rows into the report's column namespace.

    The three formatting helpers are injected because the view, the workbook and
    the PDF each format dates and links their own way — passing them in keeps
    one row-building implementation instead of three that drift.
    """
    rows = []
    for comp in components:
        rows.append({
            "_detail_url":   detail_url(comp.parent_asset),
            "_is_active":    comp.is_active,
            "purchase_date": date_str(comp.purchase_date),
            "component":     comp.label,
            "capacity":      comp.capacity_display,
            "brand":         comp.brand,
            "model":         comp.model_name,
            "serial_no":     comp.serial_number,
            "cost":          comp.cost if comp.cost is not None else "",
            "vendor":        comp.vendor.name if comp.vendor else "",
            "purchase_order": comp.purchase_order,
            "asset_tag":     comp.parent_asset.asset_tag,
            "asset_type":    comp.parent_asset.asset_type.name,
            "category":      comp.parent_asset.asset_type.category.name,
            "holder":        _holder(comp),
            "installed_on":  dt_str(comp.created_at),
            "status":        "Installed" if comp.is_active else "Removed",
            "added_by":      _added_by(comp),
        })
    return rows


def _period_key(component, basis: str, group: str) -> tuple[str, str]:
    """(sort key, label) for the period this component falls in."""
    value = component.created_at.date() if basis == "installed" else component.purchase_date
    if value is None:
        return ("", "No date")
    if group == "day":
        return (value.isoformat(), value.strftime("%d %b %Y"))
    return (value.strftime("%Y-%m"), value.strftime("%b %Y"))


def summarise(components, *, basis: str = "purchase", group: str = "month") -> dict:
    """
    Vendor-wise and date-wise totals for the report's summary card and the
    workbook's Summary sheet.

    Computed from the full result list *before* pagination, so the card totals
    the whole report rather than the page on screen — the same rule the
    office-assets summary follows.

    A row with no cost recorded still counts towards ``count``; only ``cost``
    ignores it. Reporting a spend of zero for a part whose price nobody entered
    would understate the total silently.
    """
    vendors: dict[str, dict] = {}
    periods: dict[str, dict] = {}
    parts: dict[str, dict] = {}
    total_cost = Decimal("0")
    costed = 0

    for comp in components:
        cost = comp.cost or Decimal("0")
        if comp.cost is not None:
            total_cost += comp.cost
            costed += 1

        vendor_name = comp.vendor.name if comp.vendor else "— No vendor —"
        bucket = vendors.setdefault(vendor_name, {"name": vendor_name, "count": 0, "cost": Decimal("0")})
        bucket["count"] += 1
        bucket["cost"] += cost

        sort_key, label = _period_key(comp, basis, group)
        bucket = periods.setdefault(
            sort_key, {"key": sort_key, "name": label, "count": 0, "cost": Decimal("0")}
        )
        bucket["count"] += 1
        bucket["cost"] += cost

        part_name = comp.label
        bucket = parts.setdefault(part_name, {"name": part_name, "count": 0, "cost": Decimal("0")})
        bucket["count"] += 1
        bucket["cost"] += cost

    return {
        "total": len(components),
        "total_cost": total_cost,
        "costed": costed,
        "uncosted": len(components) - costed,
        # Vendors by spend — the question "who did we buy the most from".
        "vendors": sorted(vendors.values(), key=lambda v: (-v["cost"], v["name"])),
        # Periods oldest first, so the card reads as a timeline. Undated rows
        # bucket under an empty key, which would sort before every real period,
        # so they are pushed to the end explicitly.
        "periods": sorted(periods.values(), key=lambda p: (p["key"] == "", p["key"])),
        "parts": sorted(parts.values(), key=lambda p: (-p["count"], p["name"])),
    }

